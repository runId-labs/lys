"""
Mistral AI provider implementation.

This module implements the AIProvider interface for Mistral AI,
supporting both standard chat and structured JSON responses.
"""

import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional, Type

import httpx

from lys.apps.ai.utils.providers.abstracts import AIProvider, AIResponse, AIStreamChunk, T
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIAuthError,
    AIRateLimitError,
    AIModelNotFoundError,
    AIProviderError,
    AITimeoutError,
    AIValidationError,
)

logger = logging.getLogger(__name__)


class MistralProvider(AIProvider):
    """Mistral AI provider implementation."""

    name = "mistral"
    default_base_url = "https://api.mistral.ai/v1"

    MODELS = [
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
        "codestral-latest",
        "mistral-embed",
    ]

    # Valid options that can be passed to Mistral API
    VALID_OPTIONS = {
        "temperature", "top_p", "max_tokens", "min_tokens",
        "stream", "stop", "random_seed", "safe_prompt",
        "response_format", "presence_penalty", "frequency_penalty",
    }

    # ========== Standard Chat ==========

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Send a chat request to Mistral API."""
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            **filtered_options,
        }

        if tools:
            # Strip internal fields (like _graphql) that LLM APIs don't expect
            cleaned_tools = [
                {k: v for k, v in tool.items() if not k.startswith("_")}
                for tool in tools
            ]
            payload["tools"] = cleaned_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )

            return self._parse_response(response)

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    def chat_sync(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous version using httpx sync client."""
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            **filtered_options,
        }

        if tools:
            # Strip internal fields (like _graphql) that LLM APIs don't expect
            cleaned_tools = [
                {k: v for k, v in tool.items() if not k.startswith("_")}
                for tool in tools
            ]
            payload["tools"] = cleaned_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )

            return self._parse_response(response)

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    # ========== Streaming ==========

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """Stream a chat response from Mistral API, yielding chunks."""
        base_url = self.get_base_url(config)

        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            "stream": True,
            **filtered_options,
        }

        if tools:
            cleaned_tools = [
                {k: v for k, v in tool.items() if not k.startswith("_")}
                for tool in tools
            ]
            payload["tools"] = cleaned_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                ) as response:
                    self._handle_error_status(response)

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:]  # Strip "data: " prefix
                        if data_str.strip() == "[DONE]":
                            return

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            logger.warning(f"Mistral stream: invalid JSON: {data_str}")
                            continue

                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        content = delta.get("content")
                        tool_calls = delta.get("tool_calls")

                        yield AIStreamChunk(
                            content=content,
                            tool_calls=tool_calls,
                            finish_reason=finish_reason,
                            usage=data.get("usage"),
                            model=data.get("model"),
                            provider=self.name,
                        )

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    # ========== JSON Methods ==========

    async def chat_json(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """
        Mistral: Uses json_object + schema in prompt.
        No native JSON schema support, so we inject schema description.
        """
        # Inject schema into messages
        enriched_messages = self._inject_schema_in_messages(messages, schema)

        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": enriched_messages,
            "response_format": {"type": "json_object"},
            **filtered_options,
        }

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )

            ai_response = self._parse_response(response)

            try:
                return schema.model_validate_json(ai_response.content)
            except Exception as e:
                raise AIValidationError(
                    f"Failed to validate response against schema {schema.__name__}: {e}"
                )

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    def chat_json_sync(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous version."""
        enriched_messages = self._inject_schema_in_messages(messages, schema)

        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": enriched_messages,
            "response_format": {"type": "json_object"},
            **filtered_options,
        }

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )

            ai_response = self._parse_response(response)

            try:
                return schema.model_validate_json(ai_response.content)
            except Exception as e:
                logger.warning(f"Mistral response validation failed for {schema.__name__}: {e}")
                raise AIValidationError(
                    f"Failed to validate response against schema {schema.__name__}: {e}"
                )

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    # ========== Helpers ==========

    def _handle_error_status(self, response: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        if response.status_code == 401:
            raise AIAuthError("Invalid Mistral API key")
        if response.status_code == 429:
            raise AIRateLimitError("Mistral rate limit exceeded")
        if response.status_code == 404:
            raise AIModelNotFoundError("Mistral model not found")
        if response.status_code >= 500:
            raise AIProviderError(f"Mistral server error: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Mistral API error {response.status_code}: {response.text}")
            raise AIProviderError(f"Mistral error: {response.status_code}")

    def _parse_response(self, response: httpx.Response) -> AIResponse:
        """Parse Mistral API response."""
        self._handle_error_status(response)

        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if part.get("type") == "text"
            )

        return AIResponse(
            content=content,
            tool_calls=message.get("tool_calls", []),
            usage=data.get("usage"),
            model=data.get("model"),
            provider=self.name,
        )

    @classmethod
    def get_available_models(cls) -> List[str]:
        return cls.MODELS