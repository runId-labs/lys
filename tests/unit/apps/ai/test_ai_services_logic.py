"""
Unit tests for AIService, AIToolService, and ContextToolService logic.

Tests provider registry, config caching, fallback logic, tool filtering,
and context tool registration/execution.

Isolation: All tests use inline imports + patch.object. No global state modified.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock


class TestProviderRegistry:
    """Tests for AIService provider registry — class-level dict operations."""

    def test_get_known_provider(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.mistral import MistralProvider

        provider = AIService.get_provider("mistral")
        assert isinstance(provider, MistralProvider)

    def test_get_unknown_provider_raises(self):
        from lys.apps.ai.modules.core.services import AIService

        with pytest.raises(ValueError, match="Unknown AI provider"):
            AIService.get_provider("nonexistent")

    def test_register_provider(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.abstracts import AIProvider

        class FakeProvider(AIProvider):
            name = "fake"
            default_base_url = "https://fake.ai"
            async def chat(self, *a, **kw): pass
            def chat_sync(self, *a, **kw): pass
            async def chat_json(self, *a, **kw): pass
            def chat_json_sync(self, *a, **kw): pass

        original = dict(AIService._providers)
        try:
            AIService.register_provider("fake", FakeProvider)
            assert "fake" in AIService._providers
            provider = AIService.get_provider("fake")
            assert isinstance(provider, FakeProvider)
        finally:
            AIService._providers = original

    def test_list_providers(self):
        from lys.apps.ai.modules.core.services import AIService

        providers = AIService.list_providers()
        assert "mistral" in providers
        assert isinstance(providers, list)


class TestAIServiceConfig:
    """Tests for AIService config caching and retrieval."""

    def test_get_config_caches(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIConfig

        mock_config = AIConfig()
        original_cache = AIService._config_cache
        try:
            AIService._config_cache = mock_config
            result = AIService.get_config()
            assert result is mock_config
        finally:
            AIService._config_cache = original_cache

    def test_clear_config_cache(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIConfig

        original_cache = AIService._config_cache
        try:
            AIService._config_cache = AIConfig()
            AIService.clear_config_cache()
            assert AIService._config_cache is None
        finally:
            AIService._config_cache = original_cache

    def test_get_config_no_plugin_raises(self):
        from lys.apps.ai.modules.core.services import AIService

        original_cache = AIService._config_cache
        try:
            AIService._config_cache = None
            with patch.object(AIService, "app_manager", create=True) as mock_am:
                mock_am.settings.get_plugin_config.return_value = None
                with pytest.raises(ValueError, match="not configured"):
                    AIService.get_config()
        finally:
            AIService._config_cache = original_cache


class TestChatWithFallback:
    """Tests for AIService._chat_with_fallback() retry/fallback logic."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.abstracts import AIResponse
        from lys.apps.ai.utils.providers.config import AIEndpointConfig

        expected = AIResponse(content="Hello")
        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(return_value=expected)

        endpoint = AIEndpointConfig(provider="mistral", model="test", api_key="k")

        with patch.object(AIService, "get_provider", return_value=mock_provider):
            result = await AIService._chat_with_fallback(
                [{"role": "user", "content": "hi"}], endpoint
            )

        assert result is expected

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_fallback(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.abstracts import AIResponse
        from lys.apps.ai.utils.providers.config import AIEndpointConfig
        from lys.apps.ai.utils.providers.exceptions import AIRateLimitError

        fallback_response = AIResponse(content="Fallback")
        fallback_endpoint = AIEndpointConfig(
            provider="fallback", model="fb", api_key="k"
        )
        primary_endpoint = AIEndpointConfig(
            provider="mistral", model="test", api_key="k", fallback=fallback_endpoint
        )

        mock_primary = AsyncMock()
        mock_primary.chat = AsyncMock(side_effect=AIRateLimitError("rate limited"))
        mock_fallback = AsyncMock()
        mock_fallback.chat = AsyncMock(return_value=fallback_response)

        def get_provider(name):
            if name == "mistral":
                return mock_primary
            return mock_fallback

        with patch.object(AIService, "get_provider", side_effect=get_provider):
            result = await AIService._chat_with_fallback(
                [{"role": "user", "content": "hi"}], primary_endpoint
            )

        assert result is fallback_response

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIEndpointConfig
        from lys.apps.ai.utils.providers.exceptions import AIProviderError, AIError

        endpoint = AIEndpointConfig(provider="mistral", model="test", api_key="k")

        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(side_effect=AIProviderError("server error"))

        original_delay = AIService.RETRY_DELAY
        try:
            AIService.RETRY_DELAY = 0  # Speed up test
            with patch.object(AIService, "get_provider", return_value=mock_provider):
                with pytest.raises(AIError, match="All providers failed"):
                    await AIService._chat_with_fallback(
                        [{"role": "user", "content": "hi"}], endpoint
                    )
        finally:
            AIService.RETRY_DELAY = original_delay

        assert mock_provider.chat.call_count == AIService.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_no_fallback_raises_after_rate_limit(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIEndpointConfig
        from lys.apps.ai.utils.providers.exceptions import AIRateLimitError, AIError

        endpoint = AIEndpointConfig(provider="mistral", model="test", api_key="k")

        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(side_effect=AIRateLimitError("rate limited"))

        with patch.object(AIService, "get_provider", return_value=mock_provider):
            with pytest.raises(AIError, match="All providers failed"):
                await AIService._chat_with_fallback(
                    [{"role": "user", "content": "hi"}], endpoint
                )


class TestChatJsonFallbackRetryPolicy:
    """Retry policy of AIService._chat_json_with_fallback and its sync twin.

    A schema mismatch is retried on the same endpoint; a truncated response is not,
    because the same request hits the same output limit every time.
    """

    @staticmethod
    def _endpoints():
        from lys.apps.ai.utils.providers.config import AIEndpointConfig

        fallback = AIEndpointConfig(provider="fallback", model="fb", api_key="k")
        primary = AIEndpointConfig(
            provider="mistral", model="test", api_key="k", fallback=fallback
        )
        return primary, fallback

    @staticmethod
    def _no_delay():
        from lys.apps.ai.modules.core.services import AIService

        return patch.object(AIService, "RETRY_DELAY", 0)

    @pytest.mark.asyncio
    async def test_validation_error_is_retried_then_falls_back(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.exceptions import AIValidationError

        primary_endpoint, _ = self._endpoints()
        sentinel = object()

        mock_primary = AsyncMock()
        mock_primary.chat_json = AsyncMock(side_effect=AIValidationError("bad schema"))
        mock_fallback = AsyncMock()
        mock_fallback.chat_json = AsyncMock(return_value=sentinel)

        def get_provider(name):
            return mock_primary if name == "mistral" else mock_fallback

        with self._no_delay():
            with patch.object(AIService, "get_provider", side_effect=get_provider):
                result = await AIService._chat_json_with_fallback(
                    [{"role": "user", "content": "hi"}], primary_endpoint, Mock
                )

        assert result is sentinel
        assert mock_primary.chat_json.call_count == AIService.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_truncation_falls_back_without_retrying(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.exceptions import AIResponseTruncatedError

        primary_endpoint, _ = self._endpoints()
        sentinel = object()

        mock_primary = AsyncMock()
        mock_primary.chat_json = AsyncMock(side_effect=AIResponseTruncatedError("cut off"))
        mock_fallback = AsyncMock()
        mock_fallback.chat_json = AsyncMock(return_value=sentinel)

        def get_provider(name):
            return mock_primary if name == "mistral" else mock_fallback

        with self._no_delay():
            with patch.object(AIService, "get_provider", side_effect=get_provider):
                result = await AIService._chat_json_with_fallback(
                    [{"role": "user", "content": "hi"}], primary_endpoint, Mock
                )

        assert result is sentinel
        assert mock_primary.chat_json.call_count == 1

    def test_sync_validation_error_is_retried_then_falls_back(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.exceptions import AIValidationError

        primary_endpoint, _ = self._endpoints()
        sentinel = object()

        mock_primary = Mock()
        mock_primary.chat_json_sync = Mock(side_effect=AIValidationError("bad schema"))
        mock_fallback = Mock()
        mock_fallback.chat_json_sync = Mock(return_value=sentinel)

        def get_provider(name):
            return mock_primary if name == "mistral" else mock_fallback

        with self._no_delay():
            with patch.object(AIService, "get_provider", side_effect=get_provider):
                result = AIService._chat_json_with_fallback_sync(
                    [{"role": "user", "content": "hi"}], primary_endpoint, Mock
                )

        assert result is sentinel
        assert mock_primary.chat_json_sync.call_count == AIService.MAX_RETRIES

    def test_sync_truncation_falls_back_without_retrying(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.exceptions import AIResponseTruncatedError

        primary_endpoint, _ = self._endpoints()
        sentinel = object()

        mock_primary = Mock()
        mock_primary.chat_json_sync = Mock(side_effect=AIResponseTruncatedError("cut off"))
        mock_fallback = Mock()
        mock_fallback.chat_json_sync = Mock(return_value=sentinel)

        def get_provider(name):
            return mock_primary if name == "mistral" else mock_fallback

        with self._no_delay():
            with patch.object(AIService, "get_provider", side_effect=get_provider):
                result = AIService._chat_json_with_fallback_sync(
                    [{"role": "user", "content": "hi"}], primary_endpoint, Mock
                )

        assert result is sentinel
        assert mock_primary.chat_json_sync.call_count == 1

    @pytest.mark.asyncio
    async def test_truncation_on_every_endpoint_never_retries(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.exceptions import AIError, AIResponseTruncatedError

        primary_endpoint, _ = self._endpoints()

        mock_provider = AsyncMock()
        mock_provider.chat_json = AsyncMock(side_effect=AIResponseTruncatedError("cut off"))

        with self._no_delay():
            with patch.object(AIService, "get_provider", return_value=mock_provider):
                with pytest.raises(AIError):
                    await AIService._chat_json_with_fallback(
                        [{"role": "user", "content": "hi"}], primary_endpoint, Mock
                    )

        # One call per endpoint in the chain, no retry on either.
        assert mock_provider.chat_json.call_count == 2


class TestFallbackErrorChaining:
    """The exhausted-chain AIError must carry the last provider error."""

    @pytest.mark.asyncio
    async def test_chat_error_reports_and_chains_the_cause(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIEndpointConfig
        from lys.apps.ai.utils.providers.exceptions import AIError, AIProviderError

        endpoint = AIEndpointConfig(provider="mistral", model="test", api_key="k")
        cause = AIProviderError("upstream exploded")

        mock_provider = AsyncMock()
        mock_provider.chat = AsyncMock(side_effect=cause)

        with patch.object(AIService, "RETRY_DELAY", 0):
            with patch.object(AIService, "get_provider", return_value=mock_provider):
                with pytest.raises(AIError) as exc_info:
                    await AIService._chat_with_fallback(
                        [{"role": "user", "content": "hi"}], endpoint
                    )

        assert "All providers failed" in str(exc_info.value)
        assert "upstream exploded" in str(exc_info.value)
        assert exc_info.value.__cause__ is cause

    @pytest.mark.asyncio
    async def test_chat_json_error_reports_and_chains_the_cause(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIEndpointConfig
        from lys.apps.ai.utils.providers.exceptions import AIError, AIResponseTruncatedError

        endpoint = AIEndpointConfig(provider="mistral", model="test", api_key="k")
        cause = AIResponseTruncatedError("cut off at 8192 tokens")

        mock_provider = AsyncMock()
        mock_provider.chat_json = AsyncMock(side_effect=cause)

        with patch.object(AIService, "RETRY_DELAY", 0):
            with patch.object(AIService, "get_provider", return_value=mock_provider):
                with pytest.raises(AIError) as exc_info:
                    await AIService._chat_json_with_fallback(
                        [{"role": "user", "content": "hi"}], endpoint, Mock
                    )

        assert "cut off at 8192 tokens" in str(exc_info.value)
        assert exc_info.value.__cause__ is cause

    def test_sync_chat_json_error_reports_and_chains_the_cause(self):
        from lys.apps.ai.modules.core.services import AIService
        from lys.apps.ai.utils.providers.config import AIEndpointConfig
        from lys.apps.ai.utils.providers.exceptions import AIError, AIValidationError

        endpoint = AIEndpointConfig(provider="mistral", model="test", api_key="k")
        cause = AIValidationError("schema mismatch")

        mock_provider = Mock()
        mock_provider.chat_json_sync = Mock(side_effect=cause)

        with patch.object(AIService, "RETRY_DELAY", 0):
            with patch.object(AIService, "get_provider", return_value=mock_provider):
                with pytest.raises(AIError) as exc_info:
                    AIService._chat_json_with_fallback_sync(
                        [{"role": "user", "content": "hi"}], endpoint, Mock
                    )

        assert "schema mismatch" in str(exc_info.value)
        assert exc_info.value.__cause__ is cause


class TestAIToolServiceGetAccessibleTools:
    """Tests for AIToolService.get_accessible_tools()."""

    @pytest.mark.asyncio
    async def test_super_user_gets_all_tools(self):
        from lys.apps.ai.modules.core.services import AIToolService

        original_tools = AIToolService._tools
        original_init = AIToolService._initialized
        try:
            AIToolService._tools = {
                "ws_public": {"definition": {"type": "function"}, "operation_type": "query"},
                "ws_private": {"definition": {"type": "function"}, "operation_type": "mutation"},
            }
            AIToolService._initialized = True

            result = await AIToolService.get_accessible_tools({"is_super_user": True})

            assert len(result) == 2
            names = {t["webservice"] for t in result}
            assert names == {"ws_public", "ws_private"}
        finally:
            AIToolService._tools = original_tools
            AIToolService._initialized = original_init

    @pytest.mark.asyncio
    async def test_regular_user_filtered_by_webservices(self):
        from lys.apps.ai.modules.core.services import AIToolService

        original_tools = AIToolService._tools
        original_init = AIToolService._initialized
        try:
            AIToolService._tools = {
                "ws_allowed": {"definition": {"type": "function"}, "operation_type": "query"},
                "ws_denied": {"definition": {"type": "function"}, "operation_type": "mutation"},
            }
            AIToolService._initialized = True

            connected_user = {
                "is_super_user": False,
                "webservices": {"ws_allowed": {}},
                "organizations": {}
            }
            result = await AIToolService.get_accessible_tools(connected_user)

            assert len(result) == 1
            assert result[0]["webservice"] == "ws_allowed"
        finally:
            AIToolService._tools = original_tools
            AIToolService._initialized = original_init

    @pytest.mark.asyncio
    async def test_organization_webservices_included(self):
        from lys.apps.ai.modules.core.services import AIToolService

        original_tools = AIToolService._tools
        original_init = AIToolService._initialized
        try:
            AIToolService._tools = {
                "ws_org": {"definition": {"type": "function"}, "operation_type": "query"},
                "ws_other": {"definition": {"type": "function"}, "operation_type": "mutation"},
            }
            AIToolService._initialized = True

            connected_user = {
                "is_super_user": False,
                "webservices": {},
                "organizations": {
                    "client-1": {"webservices": ["ws_org"]}
                }
            }
            result = await AIToolService.get_accessible_tools(connected_user)

            assert len(result) == 1
            assert result[0]["webservice"] == "ws_org"
        finally:
            AIToolService._tools = original_tools
            AIToolService._initialized = original_init

    @pytest.mark.asyncio
    async def test_none_user_gets_nothing(self):
        from lys.apps.ai.modules.core.services import AIToolService

        original_tools = AIToolService._tools
        original_init = AIToolService._initialized
        try:
            AIToolService._tools = {
                "ws_1": {"definition": {"type": "function"}, "operation_type": "query"},
            }
            AIToolService._initialized = True

            result = await AIToolService.get_accessible_tools(None)

            assert len(result) == 0
        finally:
            AIToolService._tools = original_tools
            AIToolService._initialized = original_init


class TestContextToolService:
    """Tests for ContextToolService register/get/execute logic."""

    def test_register_and_get(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            my_func = AsyncMock()
            ContextToolService.register("my_tool", my_func)
            assert ContextToolService.get("my_tool") is my_func
        finally:
            ContextToolService._registry = original_registry

    def test_get_missing_returns_none(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            assert ContextToolService.get("nonexistent") is None
        finally:
            ContextToolService._registry = original_registry

    @pytest.mark.asyncio
    async def test_execute_calls_function(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            my_func = AsyncMock(return_value="result data")
            ContextToolService.register("my_tool", my_func)

            result = await ContextToolService.execute(
                "my_tool", session="fake-session", access_token="test-token", company_id="c1"
            )
            assert result == "result data"
            my_func.assert_called_once_with(
                session="fake-session", access_token="test-token", company_id="c1"
            )
        finally:
            ContextToolService._registry = original_registry

    @pytest.mark.asyncio
    async def test_execute_unknown_returns_none(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            result = await ContextToolService.execute("nonexistent", session="s", access_token="t")
            assert result is None
        finally:
            ContextToolService._registry = original_registry

    @pytest.mark.asyncio
    async def test_execute_error_returns_none(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            my_func = AsyncMock(side_effect=ValueError("boom"))
            ContextToolService.register("my_tool", my_func)

            result = await ContextToolService.execute("my_tool", session="s", access_token="t")
            assert result is None
        finally:
            ContextToolService._registry = original_registry

    @pytest.mark.asyncio
    async def test_execute_all(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            func_a = AsyncMock(return_value="data_a")
            func_b = AsyncMock(return_value="data_b")
            ContextToolService.register("tool_a", func_a)
            ContextToolService.register("tool_b", func_b)

            result = await ContextToolService.execute_all(
                context_tools={"label_a": "tool_a", "label_b": "tool_b"},
                session="s",
                access_token="test-token",
                year=2024
            )
            assert result == {"label_a": "data_a", "label_b": "data_b"}
        finally:
            ContextToolService._registry = original_registry

    @pytest.mark.asyncio
    async def test_execute_all_skips_none_results(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {}
            func_a = AsyncMock(return_value="data_a")
            ContextToolService.register("tool_a", func_a)

            result = await ContextToolService.execute_all(
                context_tools={"label_a": "tool_a", "label_missing": "nonexistent"},
                session="s",
                access_token="test-token"
            )
            assert result == {"label_a": "data_a"}
            assert "label_missing" not in result
        finally:
            ContextToolService._registry = original_registry

    def test_reset(self):
        from lys.apps.ai.modules.core.services import ContextToolService

        original_registry = ContextToolService._registry
        try:
            ContextToolService._registry = {"a": "b"}
            ContextToolService.reset()
            assert ContextToolService._registry == {}
        finally:
            ContextToolService._registry = original_registry
