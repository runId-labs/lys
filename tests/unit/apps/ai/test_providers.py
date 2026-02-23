"""
Unit tests for AI providers.

Tests provider error handling with mocked HTTP responses.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import httpx

from lys.apps.ai.utils.providers import MistralProvider
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIAuthError,
    AIRateLimitError,
    AIModelNotFoundError,
    AIProviderError,
    AITimeoutError,
)
from lys.apps.ai.modules.core.services import AIService


class TestMistralProvider:
    """Tests for MistralProvider."""

    @pytest.fixture
    def provider(self):
        return MistralProvider()

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-api-key",
            timeout=30,
        )

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    def _mock_response(self, status_code: int, content: str = "", tool_calls: list = None):
        """Create a mock httpx.Response."""
        if status_code == 200:
            data = {
                "choices": [{
                    "message": {
                        "content": content,
                        "tool_calls": tool_calls or [],
                    }
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                "model": "mistral-large-latest",
            }
            response = MagicMock(spec=httpx.Response)
            response.status_code = status_code
            response.json.return_value = data
            return response
        else:
            response = MagicMock(spec=httpx.Response)
            response.status_code = status_code
            response.text = f"Error {status_code}"
            return response

    # ========== Success Cases ==========

    @pytest.mark.asyncio
    async def test_chat_success(self, provider, config, messages):
        """Test successful chat request."""
        mock_response = self._mock_response(200, content="Hello! How can I help you?")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = await provider.chat(messages, config)

            assert response.content == "Hello! How can I help you?"
            assert response.provider == "mistral"
            assert response.model == "mistral-large-latest"
            assert response.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, provider, config, messages):
        """Test chat request with tool calls in response."""
        tool_calls = [{
            "id": "call_123",
            "function": {
                "name": "get_user",
                "arguments": '{"user_id": "abc"}'
            }
        }]
        mock_response = self._mock_response(200, content="", tool_calls=tool_calls)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            response = await provider.chat(messages, config)

            assert response.tool_calls == tool_calls
            assert len(response.tool_calls) == 1

    def test_chat_sync_success(self, provider, config, messages):
        """Test successful synchronous chat request."""
        mock_response = self._mock_response(200, content="Hello sync!")

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance

            response = provider.chat_sync(messages, config)

            assert response.content == "Hello sync!"
            assert response.provider == "mistral"

    # ========== Error Cases ==========

    @pytest.mark.asyncio
    async def test_chat_auth_error(self, provider, config, messages):
        """Test that 401 response raises AIAuthError."""
        mock_response = self._mock_response(401)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AIAuthError) as exc_info:
                await provider.chat(messages, config)

            assert "Invalid Mistral API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_rate_limit_error(self, provider, config, messages):
        """Test that 429 response raises AIRateLimitError."""
        mock_response = self._mock_response(429)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AIRateLimitError) as exc_info:
                await provider.chat(messages, config)

            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_model_not_found_error(self, provider, config, messages):
        """Test that 404 response raises AIModelNotFoundError."""
        mock_response = self._mock_response(404)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AIModelNotFoundError) as exc_info:
                await provider.chat(messages, config)

            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_server_error(self, provider, config, messages):
        """Test that 5xx response raises AIProviderError."""
        mock_response = self._mock_response(500)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AIProviderError) as exc_info:
                await provider.chat(messages, config)

            assert "server error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_timeout_error(self, provider, config, messages):
        """Test that timeout raises AITimeoutError."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AITimeoutError) as exc_info:
                await provider.chat(messages, config)

            assert "timed out" in str(exc_info.value).lower()

    # ========== Sync Error Cases ==========

    def test_chat_sync_auth_error(self, provider, config, messages):
        """Test that 401 response raises AIAuthError in sync mode."""
        mock_response = self._mock_response(401)

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance

            with pytest.raises(AIAuthError):
                provider.chat_sync(messages, config)

    def test_chat_sync_timeout_error(self, provider, config, messages):
        """Test that timeout raises AITimeoutError in sync mode."""
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__enter__.return_value = mock_instance

            with pytest.raises(AITimeoutError):
                provider.chat_sync(messages, config)

    # ========== Base URL ==========

    @pytest.mark.asyncio
    async def test_custom_base_url(self, provider, messages):
        """Test that custom base_url is used."""
        config = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-key",
            base_url="https://custom.api.com/v1",
        )
        mock_response = self._mock_response(200, content="Custom URL response")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await provider.chat(messages, config)

            # Verify the custom URL was used
            call_args = mock_instance.post.call_args
            assert "custom.api.com" in call_args[0][0]

    # ========== Structured Content ==========

    @pytest.mark.asyncio
    async def test_structured_content_parsing(self, provider, config, messages):
        """Test that structured content (list format) is parsed correctly."""
        # Mistral sometimes returns content as a list of parts
        data = {
            "choices": [{
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello "},
                        {"type": "text", "text": "World!"}
                    ],
                    "tool_calls": [],
                }
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "model": "mistral-large-latest",
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = data

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await provider.chat(messages, config)

            assert result.content == "Hello World!"


class TestProviderRegistry:
    """Tests for AIService provider registry."""

    def test_get_provider_mistral(self):
        """Test getting Mistral provider via AIService."""
        provider = AIService.get_provider("mistral")
        assert isinstance(provider, MistralProvider)
        assert provider.name == "mistral"

    def test_get_provider_unknown(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AIService.get_provider("unknown_provider")

        assert "Unknown AI provider" in str(exc_info.value)
        assert "unknown_provider" in str(exc_info.value)

    def test_list_providers(self):
        """Test listing registered providers."""
        providers = AIService.list_providers()
        assert "mistral" in providers

    def test_register_custom_provider(self):
        """Test registering a custom provider via AIService."""
        from lys.apps.ai.utils.providers.abstracts import AIProvider

        class CustomProvider(AIProvider):
            name = "custom"
            default_base_url = "https://custom.api.com"

            async def chat(self, messages, config, tools=None):
                pass

            def chat_sync(self, messages, config, tools=None):
                pass

            async def chat_json(self, messages, config, schema):
                pass

            def chat_json_sync(self, messages, config, schema):
                pass

        AIService.register_provider("custom", CustomProvider)
        provider = AIService.get_provider("custom")

        assert isinstance(provider, CustomProvider)
        assert provider.name == "custom"

        # Cleanup: remove custom provider to avoid affecting other tests
        del AIService._providers["custom"]


# ========== AIStreamChunk ==========


class TestAIStreamChunk:
    """Tests for AIStreamChunk dataclass."""

    def test_default_fields_are_none(self):
        """Test that all fields default to None."""
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        chunk = AIStreamChunk()
        assert chunk.content is None
        assert chunk.tool_calls is None
        assert chunk.finish_reason is None
        assert chunk.usage is None
        assert chunk.model is None
        assert chunk.provider is None

    def test_fields_are_set(self):
        """Test that fields can be set via constructor."""
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        chunk = AIStreamChunk(
            content="Hello",
            tool_calls=[{"id": "c1"}],
            finish_reason="stop",
            usage={"prompt_tokens": 5, "completion_tokens": 2},
            model="mistral-large",
            provider="mistral",
        )
        assert chunk.content == "Hello"
        assert chunk.tool_calls == [{"id": "c1"}]
        assert chunk.finish_reason == "stop"
        assert chunk.usage == {"prompt_tokens": 5, "completion_tokens": 2}
        assert chunk.model == "mistral-large"
        assert chunk.provider == "mistral"


# ========== AIProvider.chat_stream default ==========


class TestAIProviderChatStreamDefault:
    """Tests for AIProvider.chat_stream default implementation."""

    @pytest.mark.asyncio
    async def test_chat_stream_raises_not_implemented(self):
        """Test that base class chat_stream raises NotImplementedError."""
        from lys.apps.ai.utils.providers.abstracts import AIProvider

        class MinimalProvider(AIProvider):
            name = "minimal"
            default_base_url = "https://example.com"
            async def chat(self, *a, **kw): pass
            def chat_sync(self, *a, **kw): pass
            async def chat_json(self, *a, **kw): pass
            def chat_json_sync(self, *a, **kw): pass

        provider = MinimalProvider()
        config = AIEndpointConfig(provider="minimal", model="test", api_key="k")

        with pytest.raises(NotImplementedError, match="minimal"):
            async for _ in provider.chat_stream([], config):
                pass  # pragma: no cover


# ========== MistralProvider.chat_stream ==========


class TestMistralProviderChatStream:
    """Tests for MistralProvider.chat_stream method."""

    @pytest.fixture
    def provider(self):
        return MistralProvider()

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-api-key",
            timeout=30,
        )

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    @staticmethod
    def _make_stream_mock(lines, status_code=200):
        """Create a properly nested mock for httpx async streaming."""
        async def aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = f"Error {status_code}"
        mock_response.aiter_lines = aiter_lines

        # stream() returns an async context manager whose __aenter__ yields mock_response
        stream_cm = AsyncMock()
        stream_cm.__aenter__.return_value = mock_response

        # AsyncClient() returns an async context manager whose __aenter__ yields an object with .stream()
        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = stream_cm

        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = mock_http_client

        return client_cm, mock_http_client

    @pytest.mark.asyncio
    async def test_chat_stream_text_response(self, provider, config, messages):
        """Test streaming a simple text response."""
        lines = [
            'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}],"model":"mistral-large-latest"}',
            'data: {"choices":[{"delta":{"content":" world"},"finish_reason":"stop"}],"model":"mistral-large-latest","usage":{"prompt_tokens":5,"completion_tokens":2}}',
            "data: [DONE]",
        ]

        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = []
            async for chunk in provider.chat_stream(messages, config):
                chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content == "Hello"
        assert chunks[0].provider == "mistral"
        assert chunks[1].content == " world"
        assert chunks[1].finish_reason == "stop"
        assert chunks[1].usage == {"prompt_tokens": 5, "completion_tokens": 2}

    @pytest.mark.asyncio
    async def test_chat_stream_with_tool_calls(self, provider, config, messages):
        """Test streaming a response with tool calls."""
        lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1","function":{"name":"get_user","arguments":"{\\"id\\":"}}]},"finish_reason":null}],"model":"m1"}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" \\"abc\\"}"}}]},"finish_reason":"tool_calls"}],"model":"m1"}',
            "data: [DONE]",
        ]

        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = []
            async for chunk in provider.chat_stream(messages, config):
                chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].tool_calls is not None
        assert chunks[0].tool_calls[0]["id"] == "call-1"
        assert chunks[1].finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_chat_stream_skips_non_data_lines(self, provider, config, messages):
        """Test that non-data lines (comments, empty) are skipped."""
        lines = [
            ": keep-alive",
            "",
            'data: {"choices":[{"delta":{"content":"Hi"},"finish_reason":"stop"}],"model":"m1"}',
            "data: [DONE]",
        ]

        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = []
            async for chunk in provider.chat_stream(messages, config):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].content == "Hi"

    @pytest.mark.asyncio
    async def test_chat_stream_skips_invalid_json(self, provider, config, messages):
        """Test that invalid JSON lines are skipped."""
        lines = [
            "data: {not valid json}",
            'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}],"model":"m1"}',
            "data: [DONE]",
        ]

        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = []
            async for chunk in provider.chat_stream(messages, config):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].content == "ok"

    @pytest.mark.asyncio
    async def test_chat_stream_auth_error(self, provider, config, messages):
        """Test that 401 during streaming raises AIAuthError."""
        client_cm, _ = self._make_stream_mock([], status_code=401)
        with patch("httpx.AsyncClient", return_value=client_cm):
            with pytest.raises(AIAuthError):
                async for _ in provider.chat_stream(messages, config):
                    pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_chat_stream_timeout_error(self, provider, config, messages):
        """Test that timeout during streaming raises AITimeoutError."""
        # Need to make client.stream() raise TimeoutException
        mock_http_client = MagicMock()
        mock_http_client.stream.side_effect = httpx.TimeoutException("Timeout")

        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = mock_http_client

        with patch("httpx.AsyncClient", return_value=client_cm):
            with pytest.raises(AITimeoutError):
                async for _ in provider.chat_stream(messages, config):
                    pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_chat_stream_passes_tools(self, provider, config, messages):
        """Test that tools are included in the streaming request payload."""
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        lines = [
            'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}],"model":"m1"}',
            "data: [DONE]",
        ]

        client_cm, mock_http_client = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            async for _ in provider.chat_stream(messages, config, tools=tools):
                pass

            call_kwargs = mock_http_client.stream.call_args
            payload = call_kwargs[1]["json"]
            assert payload["stream"] is True
            assert payload["tools"] == tools
            assert payload["tool_choice"] == "auto"


# ========== MistralProvider._handle_error_status ==========


class TestMistralProviderHandleErrorStatus:
    """Tests for MistralProvider._handle_error_status refactored method."""

    @pytest.fixture
    def provider(self):
        return MistralProvider()

    def test_handle_error_status_401(self, provider):
        """Test 401 raises AIAuthError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        with pytest.raises(AIAuthError):
            provider._handle_error_status(response)

    def test_handle_error_status_429(self, provider):
        """Test 429 raises AIRateLimitError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        with pytest.raises(AIRateLimitError):
            provider._handle_error_status(response)

    def test_handle_error_status_404(self, provider):
        """Test 404 raises AIModelNotFoundError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        with pytest.raises(AIModelNotFoundError):
            provider._handle_error_status(response)

    def test_handle_error_status_500(self, provider):
        """Test 500 raises AIProviderError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500
        response.text = "Internal Server Error"
        with pytest.raises(AIProviderError):
            provider._handle_error_status(response)

    def test_handle_error_status_200_no_raise(self, provider):
        """Test 200 does not raise."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        # Should not raise
        provider._handle_error_status(response)
