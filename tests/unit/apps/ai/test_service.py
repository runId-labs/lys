"""
Unit tests for AIService.

Tests fallback logic, retry behavior, and purpose-based chat.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from lys.apps.ai.utils.providers.abstracts import AIResponse
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIError,
    AIRateLimitError,
    AIProviderError,
    AIAuthError,
)
from lys.apps.ai.modules.core.services import AIService


class TestAIServiceFallback:
    """Tests for AIService fallback logic."""

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    @pytest.fixture
    def primary_config(self):
        return AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="mistral-key",
        )

    @pytest.fixture
    def config_with_fallback(self):
        fallback = AIEndpointConfig(
            provider="openai",
            model="gpt-4o",
            api_key="openai-key",
        )
        return AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="mistral-key",
            fallback=fallback,
        )

    # ========== Success Cases ==========

    @pytest.mark.asyncio
    async def test_chat_success_no_fallback_needed(self, messages, primary_config):
        """Test that successful chat doesn't trigger fallback."""
        expected_response = AIResponse(
            content="Hello!",
            provider="mistral",
            model="mistral-large-latest",
        )

        with patch.object(AIService, "get_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.chat.return_value = expected_response
            mock_get.return_value = mock_provider

            response = await AIService._chat_with_fallback(messages, primary_config)

            assert response.content == "Hello!"
            assert response.provider == "mistral"
            mock_provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_rate_limit(self, messages, config_with_fallback):
        """Test that rate limit triggers immediate fallback."""
        fallback_response = AIResponse(
            content="Fallback response",
            provider="openai",
            model="gpt-4o",
        )

        with patch.object(AIService, "get_provider") as mock_get:
            # Primary provider raises rate limit
            mock_primary = AsyncMock()
            mock_primary.chat.side_effect = AIRateLimitError("Rate limit exceeded")

            # Fallback provider succeeds
            mock_fallback = AsyncMock()
            mock_fallback.chat.return_value = fallback_response

            mock_get.side_effect = [mock_primary, mock_fallback]

            response = await AIService._chat_with_fallback(messages, config_with_fallback)

            assert response.provider == "openai"
            assert response.content == "Fallback response"

    @pytest.mark.asyncio
    async def test_fallback_on_auth_error(self, messages, config_with_fallback):
        """Test that auth error triggers fallback."""
        fallback_response = AIResponse(
            content="Fallback",
            provider="openai",
        )

        with patch.object(AIService, "get_provider") as mock_get:
            mock_primary = AsyncMock()
            mock_primary.chat.side_effect = AIAuthError("Invalid key")

            mock_fallback = AsyncMock()
            mock_fallback.chat.return_value = fallback_response

            mock_get.side_effect = [mock_primary, mock_fallback]

            response = await AIService._chat_with_fallback(messages, config_with_fallback)

            assert response.provider == "openai"

    @pytest.mark.asyncio
    async def test_retry_on_provider_error(self, messages, primary_config):
        """Test that provider error triggers retry before fallback."""
        success_response = AIResponse(content="Success after retry", provider="mistral")

        with patch.object(AIService, "get_provider") as mock_get:
            mock_provider = AsyncMock()
            # First call fails, second succeeds
            mock_provider.chat.side_effect = [
                AIProviderError("Server error"),
                success_response,
            ]
            mock_get.return_value = mock_provider

            with patch("asyncio.sleep", new_callable=AsyncMock):
                response = await AIService._chat_with_fallback(messages, primary_config)

            assert response.content == "Success after retry"
            assert mock_provider.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_then_fallback(self, messages, config_with_fallback):
        """Test that after all retries are exhausted, fallback is used."""
        fallback_response = AIResponse(content="Fallback", provider="openai")

        with patch.object(AIService, "get_provider") as mock_get:
            mock_primary = AsyncMock()
            mock_primary.chat.side_effect = AIProviderError("Server error")

            mock_fallback = AsyncMock()
            mock_fallback.chat.return_value = fallback_response

            mock_get.side_effect = [mock_primary, mock_fallback]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                response = await AIService._chat_with_fallback(messages, config_with_fallback)

            assert response.provider == "openai"
            # Primary should be called MAX_RETRIES times
            assert mock_primary.chat.call_count == AIService.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_all_providers_fail(self, messages, config_with_fallback):
        """Test that AIError is raised when all providers fail."""
        with patch.object(AIService, "get_provider") as mock_get:
            mock_primary = AsyncMock()
            mock_primary.chat.side_effect = AIError("Primary failed")

            mock_fallback = AsyncMock()
            mock_fallback.chat.side_effect = AIError("Fallback failed")

            mock_get.side_effect = [mock_primary, mock_fallback]

            with pytest.raises(AIError) as exc_info:
                await AIService._chat_with_fallback(messages, config_with_fallback)

            assert "All providers failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_fallback_configured(self, messages, primary_config):
        """Test error when no fallback and primary fails."""
        with patch.object(AIService, "get_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.chat.side_effect = AIError("Failed")
            mock_get.return_value = mock_provider

            with pytest.raises(AIError) as exc_info:
                await AIService._chat_with_fallback(messages, primary_config)

            assert "All providers failed" in str(exc_info.value)


class TestAIServiceSync:
    """Tests for synchronous AIService methods."""

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-key",
        )

    def test_chat_sync_success(self, messages, config):
        """Test synchronous chat success."""
        expected_response = AIResponse(content="Hello sync!", provider="mistral")

        with patch.object(AIService, "get_provider") as mock_get:
            mock_provider = MagicMock()
            mock_provider.chat_sync.return_value = expected_response
            mock_get.return_value = mock_provider

            response = AIService._chat_with_fallback_sync(messages, config)

            assert response.content == "Hello sync!"
            mock_provider.chat_sync.assert_called_once()

    def test_chat_sync_with_fallback(self, messages):
        """Test synchronous chat with fallback."""
        fallback = AIEndpointConfig(
            provider="openai",
            model="gpt-4o",
            api_key="openai-key",
        )
        config = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="mistral-key",
            fallback=fallback,
        )
        fallback_response = AIResponse(content="Fallback", provider="openai")

        with patch.object(AIService, "get_provider") as mock_get:
            mock_primary = MagicMock()
            mock_primary.chat_sync.side_effect = AIRateLimitError("Rate limit")

            mock_fallback = MagicMock()
            mock_fallback.chat_sync.return_value = fallback_response

            mock_get.side_effect = [mock_primary, mock_fallback]

            response = AIService._chat_with_fallback_sync(messages, config)

            assert response.provider == "openai"


class TestAIServiceChat:
    """Tests for high-level AIService.chat methods."""

    @pytest.fixture
    def messages(self):
        return [{"role": "user", "content": "Hello"}]

    @pytest.fixture
    def config(self):
        return AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-key",
            system_prompt="You are helpful.",
        )

    @pytest.mark.asyncio
    async def test_chat_adds_system_prompt(self, messages, config):
        """Test that chat adds system prompt from config."""
        expected_response = AIResponse(content="Hello!", provider="mistral")

        with patch.object(AIService, "_chat_with_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = expected_response

            await AIService.chat(messages, config)

            # Check that system prompt was prepended
            call_args = mock_fallback.call_args[0]
            sent_messages = call_args[0]
            assert sent_messages[0]["role"] == "system"
            assert sent_messages[0]["content"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_chat_without_system_prompt(self, messages):
        """Test chat when no system prompt in config."""
        config = AIEndpointConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-key",
            system_prompt=None,
        )
        expected_response = AIResponse(content="Hello!", provider="mistral")

        with patch.object(AIService, "_chat_with_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = expected_response

            await AIService.chat(messages, config)

            call_args = mock_fallback.call_args[0]
            sent_messages = call_args[0]
            # Should not have system message prepended
            assert sent_messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_passes_tools(self, messages, config):
        """Test that chat passes tools to fallback method."""
        tools = [{"type": "function", "function": {"name": "test"}}]
        expected_response = AIResponse(content="Hello!", provider="mistral")

        with patch.object(AIService, "_chat_with_fallback", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = expected_response

            await AIService.chat(messages, config, tools=tools)

            call_args = mock_fallback.call_args
            assert call_args[0][2] == tools  # Third positional argument is tools
