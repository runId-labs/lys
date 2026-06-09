"""
Unit tests for AI providers.

Tests provider error handling with mocked HTTP responses.
"""

import json
import logging

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
from pydantic import BaseModel

from lys.apps.ai.utils.providers import MistralProvider, AnthropicProvider
from lys.apps.ai.utils.providers.abstracts import AIResponse
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIAuthError,
    AIRateLimitError,
    AIModelNotFoundError,
    AIProviderError,
    AITimeoutError,
    AIValidationError,
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

    def test_get_provider_anthropic(self):
        """Test getting Anthropic provider via AIService."""
        provider = AIService.get_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)
        assert provider.name == "anthropic"

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
        assert "anthropic" in providers

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
        mock_response.aread = AsyncMock()
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


# ========== MistralProvider.chat_json / chat_json_sync ==========


class _SampleSchema(BaseModel):
    """Minimal Pydantic schema used to drive chat_json tests."""

    name: str
    age: int


class TestMistralProviderBuildJsonSchemaResponseFormat:
    """Tests for the static helper MistralProvider._build_json_schema_response_format."""

    def test_returns_native_json_schema_payload(self):
        result = MistralProvider._build_json_schema_response_format(_SampleSchema)

        assert result["type"] == "json_schema"
        assert result["json_schema"]["name"] == "_SampleSchema"
        assert result["json_schema"]["strict"] is True
        assert result["json_schema"]["schema"] == _SampleSchema.model_json_schema()


class TestMistralProviderParseResponseFinishReason:
    """Tests that MistralProvider._parse_response propagates finish_reason."""

    @pytest.fixture
    def provider(self):
        return MistralProvider()

    @staticmethod
    def _build_response(finish_reason):
        data = {
            "choices": [{
                "message": {"content": "ok", "tool_calls": []},
                "finish_reason": finish_reason,
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "model": "mistral-large-latest",
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = data
        return response

    def test_finish_reason_stop_is_propagated(self, provider):
        result = provider._parse_response(self._build_response("stop"))
        assert result.finish_reason == "stop"

    def test_finish_reason_length_is_propagated(self, provider):
        result = provider._parse_response(self._build_response("length"))
        assert result.finish_reason == "length"

    def test_missing_finish_reason_is_none(self, provider):
        data = {
            "choices": [{"message": {"content": "ok", "tool_calls": []}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 7},
            "model": "mistral-large-latest",
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = data

        result = provider._parse_response(response)
        assert result.finish_reason is None


class TestMistralProviderWarnIfNonStopFinish:
    """Tests for the static helper MistralProvider._warn_if_non_stop_finish."""

    @staticmethod
    def _ai_response(finish_reason, completion_tokens=12, content="abcdef"):
        return AIResponse(
            content=content,
            tool_calls=[],
            usage={"prompt_tokens": 5, "completion_tokens": completion_tokens},
            model="mistral-large-latest",
            provider="mistral",
            finish_reason=finish_reason,
        )

    def test_silent_when_finish_reason_is_stop(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
            MistralProvider._warn_if_non_stop_finish(self._ai_response("stop"), _SampleSchema)
        assert caplog.records == []

    def test_silent_when_finish_reason_is_none(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
            MistralProvider._warn_if_non_stop_finish(self._ai_response(None), _SampleSchema)
        assert caplog.records == []

    def test_warns_when_finish_reason_is_length(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
            MistralProvider._warn_if_non_stop_finish(self._ai_response("length"), _SampleSchema)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "_SampleSchema" in message
        assert "length" in message
        assert "completion_tokens=12" in message
        assert "content_chars=6" in message

    def test_warns_when_finish_reason_is_content_filter(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
            MistralProvider._warn_if_non_stop_finish(
                self._ai_response("content_filter", completion_tokens=None), _SampleSchema
            )

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "content_filter" in message
        assert "completion_tokens=None" in message

    def test_handles_missing_usage_dict(self, caplog):
        response = AIResponse(
            content="x",
            tool_calls=[],
            usage=None,
            model="m",
            provider="mistral",
            finish_reason="length",
        )
        with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
            MistralProvider._warn_if_non_stop_finish(response, _SampleSchema)

        assert len(caplog.records) == 1
        assert "completion_tokens=None" in caplog.records[0].getMessage()


class TestMistralProviderLogValidationFailure:
    """Tests for the static helper MistralProvider._log_validation_failure."""

    def test_logs_warning_with_full_context(self, caplog):
        ai_response = AIResponse(
            content='{"name": "Alice"}',
            tool_calls=[],
            usage={"prompt_tokens": 5, "completion_tokens": 4},
            model="mistral-large-latest",
            provider="mistral",
            finish_reason="stop",
        )
        error = ValueError("missing field 'age'")

        with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
            MistralProvider._log_validation_failure(ai_response, _SampleSchema, error)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "_SampleSchema" in message
        assert "missing field 'age'" in message
        assert "finish_reason=stop" in message
        assert "completion_tokens=4" in message
        assert f"content_chars={len(ai_response.content)}" in message

    def test_invoked_by_chat_json_on_validation_error(self, caplog):
        provider = MistralProvider()
        config = AIEndpointConfig(
            provider="mistral", model="mistral-large-latest", api_key="k", timeout=30
        )

        data = {
            "choices": [{
                "message": {"content": '{"name": "Alice"}', "tool_calls": []},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 4},
            "model": "mistral-large-latest",
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = data

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = response
            mock_client.return_value.__enter__.return_value = mock_instance

            with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
                with pytest.raises(AIValidationError):
                    provider.chat_json_sync([{"role": "user", "content": "x"}], config, _SampleSchema)

        validation_logs = [r for r in caplog.records if "validation failed" in r.getMessage()]
        assert len(validation_logs) == 1
        assert "finish_reason=stop" in validation_logs[0].getMessage()

    @pytest.mark.asyncio
    async def test_chat_json_warns_on_non_stop_finish_then_validates(self, caplog):
        """When finish_reason='length' and JSON happens to be valid, warn but don't raise."""
        provider = MistralProvider()
        config = AIEndpointConfig(
            provider="mistral", model="mistral-large-latest", api_key="k", timeout=30
        )

        data = {
            "choices": [{
                "message": {"content": '{"name": "Alice", "age": 30}', "tool_calls": []},
                "finish_reason": "length",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 99},
            "model": "mistral-large-latest",
        }
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = data

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with caplog.at_level(logging.WARNING, logger="lys.apps.ai.utils.providers.mistral"):
                result = await provider.chat_json(
                    [{"role": "user", "content": "x"}], config, _SampleSchema
                )

        assert isinstance(result, _SampleSchema)
        non_stop_logs = [r for r in caplog.records if "non-stop finish_reason" in r.getMessage()]
        assert len(non_stop_logs) == 1
        assert "length" in non_stop_logs[0].getMessage()


class TestMistralProviderChatJson:
    """Tests for MistralProvider.chat_json (async) and chat_json_sync."""

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
        return [{"role": "user", "content": "Give me a person"}]

    @staticmethod
    def _mock_json_response(status_code: int, content: str = ""):
        """Create a mock httpx.Response for the /chat/completions endpoint."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        if status_code == 200:
            response.json.return_value = {
                "choices": [{
                    "message": {"content": content, "tool_calls": []},
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                "model": "mistral-large-latest",
            }
        else:
            response.text = f"Error {status_code}"
        return response

    # ---------- async ----------

    @pytest.mark.asyncio
    async def test_chat_json_success_returns_validated_model(self, provider, config, messages):
        mock_response = self._mock_json_response(200, content='{"name": "Alice", "age": 30}')

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await provider.chat_json(messages, config, _SampleSchema)

            assert isinstance(result, _SampleSchema)
            assert result.name == "Alice"
            assert result.age == 30

    @pytest.mark.asyncio
    async def test_chat_json_payload_uses_native_json_schema(self, provider, config, messages):
        """The request must use response_format json_schema and forward messages as-is."""
        mock_response = self._mock_json_response(200, content='{"name": "Bob", "age": 5}')

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await provider.chat_json(messages, config, _SampleSchema)

            payload = mock_instance.post.call_args[1]["json"]
            assert payload["model"] == "mistral-large-latest"
            # No schema injection — messages forwarded unchanged
            assert payload["messages"] == messages
            assert payload["response_format"]["type"] == "json_schema"
            assert payload["response_format"]["json_schema"]["name"] == "_SampleSchema"
            assert payload["response_format"]["json_schema"]["strict"] is True
            assert payload["response_format"]["json_schema"]["schema"] == _SampleSchema.model_json_schema()

    @pytest.mark.asyncio
    async def test_chat_json_invalid_response_raises_validation_error(self, provider, config, messages):
        mock_response = self._mock_json_response(200, content='{"name": "Alice"}')  # missing age

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AIValidationError) as exc_info:
                await provider.chat_json(messages, config, _SampleSchema)

            assert "_SampleSchema" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_json_auth_error(self, provider, config, messages):
        mock_response = self._mock_json_response(401)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AIAuthError):
                await provider.chat_json(messages, config, _SampleSchema)

    @pytest.mark.asyncio
    async def test_chat_json_timeout(self, provider, config, messages):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__aenter__.return_value = mock_instance

            with pytest.raises(AITimeoutError):
                await provider.chat_json(messages, config, _SampleSchema)

    # ---------- sync ----------

    def test_chat_json_sync_success_returns_validated_model(self, provider, config, messages):
        mock_response = self._mock_json_response(200, content='{"name": "Carol", "age": 42}')

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance

            result = provider.chat_json_sync(messages, config, _SampleSchema)

            assert isinstance(result, _SampleSchema)
            assert result.name == "Carol"
            assert result.age == 42

    def test_chat_json_sync_payload_uses_native_json_schema(self, provider, config, messages):
        mock_response = self._mock_json_response(200, content='{"name": "Dan", "age": 7}')

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance

            provider.chat_json_sync(messages, config, _SampleSchema)

            payload = mock_instance.post.call_args[1]["json"]
            assert payload["messages"] == messages
            assert payload["response_format"]["type"] == "json_schema"
            assert payload["response_format"]["json_schema"]["strict"] is True
            assert payload["response_format"]["json_schema"]["schema"] == _SampleSchema.model_json_schema()

    def test_chat_json_sync_invalid_response_raises_validation_error(self, provider, config, messages):
        mock_response = self._mock_json_response(200, content='{"name": "Dan"}')  # missing age

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance

            with pytest.raises(AIValidationError):
                provider.chat_json_sync(messages, config, _SampleSchema)

    def test_chat_json_sync_auth_error(self, provider, config, messages):
        mock_response = self._mock_json_response(401)

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance

            with pytest.raises(AIAuthError):
                provider.chat_json_sync(messages, config, _SampleSchema)

    def test_chat_json_sync_timeout(self, provider, config, messages):
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__enter__.return_value = mock_instance

            with pytest.raises(AITimeoutError):
                provider.chat_json_sync(messages, config, _SampleSchema)


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


# ========== AnthropicProvider ==========


class TestAnthropicProviderTranslation:
    """Tests for AnthropicProvider message/tool/payload translation."""

    @pytest.fixture
    def provider(self):
        return AnthropicProvider()

    def _config(self, model="claude-opus-4-8", options=None):
        return AIEndpointConfig(
            provider="anthropic",
            model=model,
            api_key="test-api-key",
            timeout=30,
            options=options or {},
        )

    def test_prepare_drops_sampling_params_on_opus(self, provider, caplog):
        """temperature/top_p/top_k are dropped (400 on Opus 4.7+) with a warning."""
        config = self._config(
            "claude-opus-4-8",
            {"temperature": 0.7, "top_p": 0.9, "top_k": 5, "max_tokens": 1000},
        )
        with caplog.at_level(logging.WARNING):
            payload, _, _ = provider._prepare([{"role": "user", "content": "hi"}], config)
        assert "temperature" not in payload
        assert "top_p" not in payload
        assert "top_k" not in payload
        assert payload["max_tokens"] == 1000
        assert "rejects sampling parameters" in caplog.text

    def test_prepare_keeps_sampling_params_on_sonnet(self, provider):
        """Sonnet 4.6 still accepts temperature, so it must be forwarded."""
        config = self._config("claude-sonnet-4-6", {"temperature": 0.7})
        payload, _, _ = provider._prepare([{"role": "user", "content": "hi"}], config)
        assert payload["temperature"] == 0.7

    def test_prepare_remaps_stop_to_stop_sequences(self, provider):
        config = self._config("claude-sonnet-4-6", {"stop": ["END"]})
        payload, _, _ = provider._prepare([{"role": "user", "content": "hi"}], config)
        assert payload["stop_sequences"] == ["END"]
        assert "stop" not in payload

    def test_prepare_default_max_tokens(self, provider):
        config = self._config("claude-sonnet-4-6")
        payload, _, _ = provider._prepare([{"role": "user", "content": "hi"}], config)
        assert payload["max_tokens"] == 8192

    def test_prepare_headers(self, provider):
        config = self._config("claude-sonnet-4-6")
        _, headers, _ = provider._prepare([{"role": "user", "content": "hi"}], config)
        assert headers["x-api-key"] == "test-api-key"
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["content-type"] == "application/json"

    def test_prepare_system_sent_as_cacheable_block(self, provider):
        """The system prompt is sent as a cache_control: ephemeral text block."""
        config = self._config("claude-sonnet-4-6")
        payload, _, _ = provider._prepare(
            [{"role": "system", "content": "You are helpful."},
             {"role": "user", "content": "hi"}],
            config,
        )
        assert payload["system"] == [{
            "type": "text",
            "text": "You are helpful.",
            "cache_control": {"type": "ephemeral"},
        }]

    def test_prepare_no_system_key_without_system_message(self, provider):
        config = self._config("claude-sonnet-4-6")
        payload, _, _ = provider._prepare([{"role": "user", "content": "hi"}], config)
        assert "system" not in payload

    def test_prepare_tools_default_tool_choice_auto(self, provider):
        config = self._config("claude-sonnet-4-6")
        tools = [{"type": "function", "function": {"name": "f", "parameters": {"type": "object"}}}]
        payload, _, _ = provider._prepare(
            [{"role": "user", "content": "hi"}], config, tools=tools,
        )
        assert payload["tools"][0]["name"] == "f"
        assert payload["tool_choice"] == {"type": "auto"}

    def test_prepare_stream_flag(self, provider):
        config = self._config("claude-sonnet-4-6")
        payload, _, _ = provider._prepare(
            [{"role": "user", "content": "hi"}], config, stream=True,
        )
        assert payload["stream"] is True

    def test_translate_messages_merges_system(self, provider):
        """Multiple system messages are concatenated, not dropped."""
        system, msgs = AnthropicProvider._translate_messages([
            {"role": "system", "content": "Base prompt."},
            {"role": "system", "content": "Conversation prompt."},
            {"role": "user", "content": "hello"},
        ])
        assert system == "Base prompt.\n\nConversation prompt."
        assert msgs == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]

    def test_translate_messages_no_system(self, provider):
        system, _ = AnthropicProvider._translate_messages([{"role": "user", "content": "x"}])
        assert system is None

    def test_translate_messages_assistant_tool_calls(self, provider):
        """Assistant tool_calls become tool_use blocks with parsed input."""
        _, msgs = AnthropicProvider._translate_messages([
            {"role": "user", "content": "do it"},
            {"role": "assistant", "content": "sure", "tool_calls": [
                {"id": "call-1", "function": {"name": "f", "arguments": '{"a": 1}'}},
            ]},
            {"role": "tool", "tool_call_id": "call-1", "content": "result"},
        ])
        assistant = msgs[1]
        assert assistant["role"] == "assistant"
        assert assistant["content"][0] == {"type": "text", "text": "sure"}
        tool_use = assistant["content"][1]
        assert tool_use == {"type": "tool_use", "id": "call-1", "name": "f", "input": {"a": 1}}
        tool_result = msgs[2]["content"][0]
        assert tool_result == {
            "type": "tool_result", "tool_use_id": "call-1", "content": "result",
        }

    def test_translate_messages_merges_consecutive_tool_results(self, provider):
        """Consecutive tool messages collapse into a single user turn."""
        _, msgs = AnthropicProvider._translate_messages([
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "function": {"name": "f", "arguments": "{}"}},
                {"id": "c2", "function": {"name": "g", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "c1", "content": "r1"},
            {"role": "tool", "tool_call_id": "c2", "content": "r2"},
        ])
        # One assistant turn, then one user turn holding both tool_results.
        assert len(msgs) == 2
        assert msgs[1]["role"] == "user"
        assert len(msgs[1]["content"]) == 2

    def test_translate_tools_openai_shape(self, provider):
        tools = [{"type": "function", "function": {
            "name": "f", "description": "d", "parameters": {"type": "object", "properties": {}},
        }, "_graphql": "internal"}]
        out = AnthropicProvider._translate_tools(tools)
        assert out == [{
            "name": "f", "description": "d",
            "input_schema": {"type": "object", "properties": {}},
        }]

    def test_translate_tools_already_anthropic(self, provider):
        tools = [{"name": "f", "input_schema": {"type": "object"}, "_x": 1}]
        out = AnthropicProvider._translate_tools(tools)
        assert out == [{"name": "f", "input_schema": {"type": "object"}}]

    def test_safe_json_variants(self, provider):
        assert AnthropicProvider._safe_json('{"a": 1}') == {"a": 1}
        assert AnthropicProvider._safe_json({"a": 1}) == {"a": 1}
        assert AnthropicProvider._safe_json("not json") == {}
        assert AnthropicProvider._safe_json("[1, 2]") == {}

    def test_map_finish_reason(self, provider):
        assert AnthropicProvider._map_finish_reason("end_turn") == "stop"
        assert AnthropicProvider._map_finish_reason("max_tokens") == "length"
        assert AnthropicProvider._map_finish_reason("tool_use") == "tool_calls"
        assert AnthropicProvider._map_finish_reason(None) is None
        assert AnthropicProvider._map_finish_reason("other") == "other"

    def test_normalize_usage(self, provider):
        assert AnthropicProvider._normalize_usage(
            {"input_tokens": 10, "output_tokens": 5}
        ) == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        assert AnthropicProvider._normalize_usage(None) is None
        assert AnthropicProvider._normalize_usage({}) is None

    def test_get_available_models(self, provider):
        assert "claude-opus-4-8" in AnthropicProvider.get_available_models()

    def test_rejects_sampling_params(self, provider):
        assert AnthropicProvider._rejects_sampling_params("claude-opus-4-8") is True
        assert AnthropicProvider._rejects_sampling_params("claude-opus-4-7") is True
        assert AnthropicProvider._rejects_sampling_params("claude-sonnet-4-6") is False


class TestAnthropicProviderChat:
    """Tests for AnthropicProvider.chat / chat_sync response parsing and errors."""

    @pytest.fixture
    def provider(self):
        return AnthropicProvider()

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="anthropic", model="claude-opus-4-8", api_key="k", timeout=30,
        )

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    @staticmethod
    def _mock_response(status_code, content_blocks=None, stop_reason="end_turn"):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        if status_code == 200:
            response.json.return_value = {
                "content": content_blocks or [{"type": "text", "text": "Hi"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "model": "claude-opus-4-8",
                "stop_reason": stop_reason,
            }
        else:
            response.text = f"Error {status_code}"
        return response

    @pytest.mark.asyncio
    async def test_chat_success(self, provider, config, messages):
        mock_response = self._mock_response(200, [{"type": "text", "text": "Hello there"}])
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            result = await provider.chat(messages, config)
        assert isinstance(result, AIResponse)
        assert result.content == "Hello there"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        assert result.finish_reason == "stop"
        assert result.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_parses_tool_use(self, provider, config, messages):
        blocks = [
            {"type": "text", "text": "calling"},
            {"type": "tool_use", "id": "tu-1", "name": "f", "input": {"a": 1}},
        ]
        mock_response = self._mock_response(200, blocks, stop_reason="tool_use")
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            result = await provider.chat(messages, config)
        assert result.content == "calling"
        assert result.tool_calls[0]["id"] == "tu-1"
        assert result.tool_calls[0]["function"]["name"] == "f"
        assert json.loads(result.tool_calls[0]["function"]["arguments"]) == {"a": 1}
        assert result.finish_reason == "tool_calls"

    def test_chat_sync_success(self, provider, config, messages):
        mock_response = self._mock_response(200, [{"type": "text", "text": "Sync hi"}])
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance
            result = provider.chat_sync(messages, config)
        assert result.content == "Sync hi"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status,exc", [
        (401, AIAuthError), (429, AIRateLimitError),
        (404, AIModelNotFoundError), (500, AIProviderError),
    ])
    async def test_chat_error_statuses(self, provider, config, messages, status, exc):
        mock_response = self._mock_response(status)
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            with pytest.raises(exc):
                await provider.chat(messages, config)

    @pytest.mark.asyncio
    async def test_chat_timeout(self, provider, config, messages):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__aenter__.return_value = mock_instance
            with pytest.raises(AITimeoutError):
                await provider.chat(messages, config)


class TestAnthropicProviderChatStream:
    """Tests for AnthropicProvider.chat_stream SSE translation."""

    @pytest.fixture
    def provider(self):
        return AnthropicProvider()

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="anthropic", model="claude-opus-4-8", api_key="k", timeout=30,
        )

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    @staticmethod
    def _make_stream_mock(lines, status_code=200):
        async def aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = f"Error {status_code}"
        mock_response.aread = AsyncMock()
        mock_response.aiter_lines = aiter_lines

        stream_cm = AsyncMock()
        stream_cm.__aenter__.return_value = mock_response

        mock_http_client = MagicMock()
        mock_http_client.stream.return_value = stream_cm

        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = mock_http_client
        return client_cm, mock_http_client

    @pytest.mark.asyncio
    async def test_stream_text_and_usage(self, provider, config, messages):
        """input_tokens from message_start merges into the final usage chunk."""
        lines = [
            'data: {"type":"message_start","message":{"usage":{"input_tokens":42}}}',
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi"}}',
            'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":13}}',
            'data: {"type":"message_stop"}',
        ]
        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = [c async for c in provider.chat_stream(messages, config)]
        # message_start and message_stop forward nothing.
        assert len(chunks) == 2
        assert chunks[0].content == "Hi"
        final = chunks[1]
        assert final.finish_reason == "stop"
        assert final.usage == {
            "prompt_tokens": 42, "completion_tokens": 13, "total_tokens": 55,
        }

    @pytest.mark.asyncio
    async def test_stream_tool_use(self, provider, config, messages):
        lines = [
            'data: {"type":"content_block_start","index":1,'
            '"content_block":{"type":"tool_use","id":"tu-1","name":"f"}}',
            'data: {"type":"content_block_delta","index":1,'
            '"delta":{"type":"input_json_delta","partial_json":"{\\"a\\":1}"}}',
            'data: {"type":"content_block_stop","index":1}',
        ]
        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = [c async for c in provider.chat_stream(messages, config)]
        assert chunks[0].tool_calls[0]["id"] == "tu-1"
        assert chunks[0].tool_calls[0]["function"]["name"] == "f"
        assert chunks[1].tool_calls[0]["function"]["arguments"] == '{"a":1}'
        # content_block_stop forwards nothing because input was seen.
        assert len(chunks) == 2

    @pytest.mark.asyncio
    async def test_stream_tool_use_empty_args_backfills(self, provider, config, messages):
        """A tool_use with no input_json_delta backfills '{}' on content_block_stop."""
        lines = [
            'data: {"type":"content_block_start","index":0,'
            '"content_block":{"type":"tool_use","id":"tu-1","name":"f"}}',
            'data: {"type":"content_block_stop","index":0}',
        ]
        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = [c async for c in provider.chat_stream(messages, config)]
        assert len(chunks) == 2
        assert chunks[1].tool_calls[0]["function"]["arguments"] == "{}"

    @pytest.mark.asyncio
    async def test_stream_skips_non_data_and_invalid_json(self, provider, config, messages):
        lines = [
            ": ping",
            "data: {not json}",
            'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"ok"}}',
        ]
        client_cm, _ = self._make_stream_mock(lines)
        with patch("httpx.AsyncClient", return_value=client_cm):
            chunks = [c async for c in provider.chat_stream(messages, config)]
        assert len(chunks) == 1
        assert chunks[0].content == "ok"

    @pytest.mark.asyncio
    async def test_stream_auth_error(self, provider, config, messages):
        client_cm, _ = self._make_stream_mock([], status_code=401)
        with patch("httpx.AsyncClient", return_value=client_cm):
            with pytest.raises(AIAuthError):
                async for _ in provider.chat_stream(messages, config):
                    pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_stream_timeout(self, provider, config, messages):
        mock_http_client = MagicMock()
        mock_http_client.stream.side_effect = httpx.TimeoutException("Timeout")
        client_cm = AsyncMock()
        client_cm.__aenter__.return_value = mock_http_client
        with patch("httpx.AsyncClient", return_value=client_cm):
            with pytest.raises(AITimeoutError):
                async for _ in provider.chat_stream(messages, config):
                    pass  # pragma: no cover


class TestAnthropicProviderChatJson:
    """Tests for AnthropicProvider.chat_json forced-tool structured output."""

    @pytest.fixture
    def provider(self):
        return AnthropicProvider()

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="anthropic", model="claude-opus-4-8", api_key="k", timeout=30,
        )

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Give me a person"}]

    @staticmethod
    def _mock_json_response(status_code, tool_input=None):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        if status_code == 200:
            content = []
            if tool_input is not None:
                content = [{"type": "tool_use", "id": "tu-1",
                            "name": "submit__sampleschema", "input": tool_input}]
            response.json.return_value = {
                "content": content,
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "model": "claude-opus-4-8",
                "stop_reason": "tool_use",
            }
        else:
            response.text = f"Error {status_code}"
        return response

    @pytest.mark.asyncio
    async def test_chat_json_success(self, provider, config, messages):
        mock_response = self._mock_json_response(200, {"name": "Alice", "age": 30})
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            result = await provider.chat_json(messages, config, _SampleSchema)
        assert isinstance(result, _SampleSchema)
        assert result.name == "Alice"
        assert result.age == 30

    @pytest.mark.asyncio
    async def test_chat_json_payload_forces_tool(self, provider, config, messages):
        mock_response = self._mock_json_response(200, {"name": "Bob", "age": 5})
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            await provider.chat_json(messages, config, _SampleSchema)
            payload = mock_instance.post.call_args[1]["json"]
        assert payload["tool_choice"]["type"] == "tool"
        assert payload["tools"][0]["name"] == payload["tool_choice"]["name"]
        assert "input_schema" in payload["tools"][0]

    @pytest.mark.asyncio
    async def test_chat_json_no_tool_use_raises(self, provider, config, messages):
        mock_response = self._mock_json_response(200, tool_input=None)
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            with pytest.raises(AIValidationError):
                await provider.chat_json(messages, config, _SampleSchema)

    @pytest.mark.asyncio
    async def test_chat_json_invalid_input_raises(self, provider, config, messages):
        mock_response = self._mock_json_response(200, {"name": "Alice"})  # missing age
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            with pytest.raises(AIValidationError):
                await provider.chat_json(messages, config, _SampleSchema)

    def test_chat_json_sync_success(self, provider, config, messages):
        mock_response = self._mock_json_response(200, {"name": "Carol", "age": 22})
        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_instance
            result = provider.chat_json_sync(messages, config, _SampleSchema)
        assert result.name == "Carol"
