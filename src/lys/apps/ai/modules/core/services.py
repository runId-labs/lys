"""
AI Service with multi-provider support.

This module provides the main AIService class for interacting with
AI providers using purpose-based configuration.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Type, TypeVar

from pydantic import BaseModel

from lys.apps.ai.utils.providers.abstracts import AIProvider, AIResponse
from lys.apps.ai.utils.providers.config import AIEndpointConfig, parse_plugin_config, AIConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIError,
    AIRateLimitError,
    AIProviderError,
)
from lys.apps.ai.utils.providers.mistral import MistralProvider
from lys.core.registries import register_service
from lys.core.services import Service

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Plugin name for AI configuration
AI_PLUGIN_NAME = "ai"


@register_service()
class AIService(Service):
    """
    Service for AI/LLM integration with multi-provider support.

    This service provides:
    - Purpose-based endpoint configuration via plugin
    - Automatic retry on provider errors
    - Optional fallback to secondary providers
    - Both async and sync methods for Celery workers
    - Structured JSON responses with Pydantic validation
    - Provider registry that can be overridden via inheritance

    Configuration via plugin:
        settings.configure_plugin("ai",
            _keys={"mistral": "sk-..."},
            chatbot={
                "provider": "mistral",
                "model": "mistral-large-latest",
                "timeout": 30,
            },
        )

    Usage:
        ai_service = app_manager.get_service("ai")

        # Chat with purpose
        response = await ai_service.chat_with_purpose(messages, "chatbot")

        # Or with explicit config
        config = ai_service.get_endpoint("chatbot")
        response = await ai_service.chat(messages, config)

    Extending with custom providers:
        # Option 1: Override via inheritance
        class MyAIService(AIService):
            _providers = {
                **AIService._providers,
                "custom": MyCustomProvider,
            }

        # Option 2: Register at runtime
        AIService.register_provider("custom", MyCustomProvider)
    """

    service_name = "ai"

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    # Cached config
    _config_cache: Optional[AIConfig] = None

    # Provider registry - can be overridden via inheritance
    _providers: Dict[str, Type[AIProvider]] = {
        "mistral": MistralProvider,
    }

    # ========== Provider Registry ==========

    @classmethod
    def get_provider(cls, name: str) -> AIProvider:
        """
        Get provider instance by name.

        Args:
            name: Provider name (e.g., "mistral", "openai")

        Returns:
            AIProvider instance

        Raises:
            ValueError: If provider is not registered
        """
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(f"Unknown AI provider: {name}. Available: {available}")
        return cls._providers[name]()

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[AIProvider]):
        """
        Register or replace a provider.

        Args:
            name: Provider name
            provider_class: Provider class (must inherit from AIProvider)
        """
        cls._providers[name] = provider_class

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    # ========== Configuration ==========

    @classmethod
    def get_config(cls) -> AIConfig:
        """
        Get parsed AI configuration from plugin.

        Returns:
            AIConfig instance with all endpoints
        """
        if cls._config_cache is not None:
            return cls._config_cache

        plugin_config = cls.app_manager.settings.get_plugin_config(AI_PLUGIN_NAME)
        if not plugin_config:
            raise ValueError(
                f"AI plugin not configured. Use settings.configure_plugin('{AI_PLUGIN_NAME}', ...)"
            )

        cls._config_cache = parse_plugin_config(plugin_config)
        return cls._config_cache

    @classmethod
    def get_endpoint(cls, purpose: str) -> AIEndpointConfig:
        """
        Get endpoint configuration for a purpose.

        Args:
            purpose: Purpose name (e.g., "chatbot", "analysis")

        Returns:
            AIEndpointConfig with resolved API key
        """
        return cls.get_config().get_endpoint(purpose)

    @classmethod
    def clear_config_cache(cls):
        """Clear the config cache to force reload."""
        cls._config_cache = None

    # ========== Purpose-based Chat (convenience) ==========

    @classmethod
    async def chat_with_purpose(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """
        Chat using a configured purpose.

        Args:
            messages: Conversation messages
            purpose: Purpose name (e.g., "chatbot", "analysis")
            tools: Optional tool definitions

        Returns:
            AIResponse
        """
        config = cls.get_endpoint(purpose)
        return await cls.chat(messages, config, tools)

    @classmethod
    def chat_with_purpose_sync(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous version for Celery workers."""
        config = cls.get_endpoint(purpose)
        return cls.chat_sync(messages, config, tools)

    # ========== Standard Chat ==========

    @classmethod
    async def chat(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """
        Send a chat request using the specified endpoint configuration.

        Args:
            messages: Conversation messages
            config: Endpoint configuration (from settings.ai.get_endpoint)
            tools: Optional tool definitions for function calling

        Returns:
            AIResponse with content, tool_calls, usage, etc.

        Raises:
            AIError: Provider errors after retries/fallback exhausted
        """
        # Add system prompt from config if present
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return await cls._chat_with_fallback(messages, config, tools)

    @classmethod
    def chat_sync(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous version for Celery workers."""
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return cls._chat_with_fallback_sync(messages, config, tools)

    # ========== Structured JSON Chat ==========

    @classmethod
    async def chat_json(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """
        Chat with structured JSON response validated against a Pydantic schema.

        Args:
            messages: Conversation messages
            config: Endpoint configuration
            schema: Pydantic model class for response validation

        Returns:
            Validated Pydantic model instance

        Raises:
            AIValidationError: Response doesn't match schema
            AIError: Provider errors after retries/fallback exhausted
        """
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return await cls._chat_json_with_fallback(messages, config, schema)

    @classmethod
    def chat_json_sync(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous version for Celery workers."""
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages

        return cls._chat_json_with_fallback_sync(messages, config, schema)

    # ========== Fallback Logic ==========

    @classmethod
    async def _chat_with_fallback(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Execute chat with retry and fallback logic."""
        current_endpoint = endpoint

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return await provider.chat(messages, current_endpoint, tools)

                except AIRateLimitError:
                    # Rate limit → try fallback immediately
                    logger.warning(
                        f"Rate limit on {current_endpoint.provider}, trying fallback"
                    )
                    break

                except AIProviderError as e:
                    # Server error → retry
                    if retry < cls.MAX_RETRIES - 1:
                        logger.warning(
                            f"Provider error (attempt {retry + 1}): {e}, retrying..."
                        )
                        await asyncio.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        logger.error(
                            f"Provider error after {cls.MAX_RETRIES} retries: {e}"
                        )
                        break

                except AIError:
                    # Other AI errors → don't retry, try fallback
                    break

            # Try fallback if configured
            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}"
                )

        raise AIError("All providers failed")

    @classmethod
    def _chat_with_fallback_sync(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous fallback logic."""
        current_endpoint = endpoint

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return provider.chat_sync(messages, current_endpoint, tools)

                except AIRateLimitError:
                    break

                except AIProviderError as e:
                    if retry < cls.MAX_RETRIES - 1:
                        time.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        break

                except AIError:
                    break

            current_endpoint = current_endpoint.fallback

        raise AIError("All providers failed")

    @classmethod
    async def _chat_json_with_fallback(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Execute chat_json with retry and fallback logic."""
        current_endpoint = endpoint

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return await provider.chat_json(messages, current_endpoint, schema)

                except AIRateLimitError:
                    logger.warning(
                        f"Rate limit on {current_endpoint.provider}, trying fallback"
                    )
                    break

                except AIProviderError as e:
                    if retry < cls.MAX_RETRIES - 1:
                        logger.warning(
                            f"Provider error (attempt {retry + 1}): {e}, retrying..."
                        )
                        await asyncio.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        logger.error(
                            f"Provider error after {cls.MAX_RETRIES} retries: {e}"
                        )
                        break

                except AIError:
                    break

            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}"
                )

        raise AIError("All providers failed")

    @classmethod
    def _chat_json_with_fallback_sync(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous fallback logic for chat_json."""
        current_endpoint = endpoint

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return provider.chat_json_sync(messages, current_endpoint, schema)

                except AIRateLimitError:
                    break

                except AIProviderError as e:
                    if retry < cls.MAX_RETRIES - 1:
                        time.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        break

                except AIError:
                    break

            current_endpoint = current_endpoint.fallback

        raise AIError("All providers failed")