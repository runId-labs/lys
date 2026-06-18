"""
Mistral AI provider implementation.

This module implements the AIProvider interface for Mistral AI,
supporting both standard chat and structured JSON responses.
"""

import base64
import hashlib
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

    @staticmethod
    def _cache_key_field(messages: List[Dict[str, Any]]) -> Dict[str, str]:
        """Stable ``prompt_cache_key`` derived from the system prompt.

        Mistral caches on the shared request prefix; passing a stable key for
        requests that share the same system prompt raises the cache-hit rate
        (cached input tokens are billed at ~10%). Returns {} when there is no
        string system message.
        """
        system = next(
            (m.get("content") for m in messages if m.get("role") == "system"), None
        )
        if not isinstance(system, str) or not system:
            return {}
        digest = hashlib.sha1(system.encode("utf-8")).hexdigest()[:32]
        return {"prompt_cache_key": f"sys-{digest}"}

    @staticmethod
    def _flatten_system(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten structured (segmented) system content into a plain string.

        The sanitizer may emit a system message whose content is an ordered list of
        ``{"text", "cache"}`` segments (for providers that support prompt-cache
        breakpoints). Mistral takes a single string, so join the segment texts.
        """
        flattened: List[Dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content")
            if (isinstance(content, list) and content
                    and isinstance(content[0], dict) and "text" in content[0]):
                msg = {**msg, "content": "\n\n".join(seg.get("text", "") for seg in content)}
            flattened.append(msg)
        return flattened

    # ========== Standard Chat ==========

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Send a chat request to Mistral API."""
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            **self._cache_key_field(messages),
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
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            **self._cache_key_field(messages),
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
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            "stream": True,
            **self._cache_key_field(messages),
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
                    if response.status_code != 200:
                        await response.aread()
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
        """Send a chat request expecting a JSON response constrained by a Pydantic schema.

        Uses Mistral's native ``response_format: {"type": "json_schema", ...}`` mode. The schema
        constraint is applied directly by the decoder rather than by injecting schema text into
        the system prompt.

        Args:
            messages: Conversation history forwarded to Mistral as-is.
            config: Endpoint configuration (model, api_key, timeout, options).
            schema: Pydantic model class describing the expected response structure.

        Returns:
            A validated instance of ``schema``.

        Raises:
            AIAuthError, AIRateLimitError, AIModelNotFoundError, AIProviderError: Provider errors.
            AITimeoutError: Request exceeded ``config.timeout``.
            AIValidationError: Response could not be validated against ``schema``.
        """
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            "response_format": self._build_json_schema_response_format(schema),
            **self._cache_key_field(messages),
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
            self._warn_if_non_stop_finish(ai_response, schema)

            try:
                return schema.model_validate_json(ai_response.content)
            except Exception as e:
                self._log_validation_failure(ai_response, schema, e)
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
        """Synchronous version of :meth:`chat_json` for Celery workers.

        Uses Mistral's native ``response_format: {"type": "json_schema", ...}`` mode.
        See :meth:`chat_json` for details on parameters, return value, and exceptions.
        """
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            "response_format": self._build_json_schema_response_format(schema),
            **self._cache_key_field(messages),
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
            self._warn_if_non_stop_finish(ai_response, schema)

            try:
                return schema.model_validate_json(ai_response.content)
            except Exception as e:
                self._log_validation_failure(ai_response, schema, e)
                raise AIValidationError(
                    f"Failed to validate response against schema {schema.__name__}: {e}"
                )

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    # ========== OCR ==========

    def ocr_sync(
        self,
        content: bytes,
        mime_type: str,
        config: AIEndpointConfig,
    ) -> str:
        """Synchronous OCR via Mistral's ``/ocr`` endpoint. Returns page markdown.

        Mistral's chat models do not OCR; this calls the dedicated OCR endpoint,
        reusing the resolved api_key + base_url. The model comes from the config
        (e.g. ``mistral-ocr-latest``).
        """
        base_url = self.get_base_url(config)
        payload = {
            "model": config.model,
            "document": self._ocr_document(content, mime_type),
            "include_image_base64": False,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/ocr",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )
            return self._parse_ocr_response(response)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    async def ocr(
        self,
        content: bytes,
        mime_type: str,
        config: AIEndpointConfig,
    ) -> str:
        """Async OCR via Mistral's ``/ocr`` endpoint. See :meth:`ocr_sync`."""
        base_url = self.get_base_url(config)
        payload = {
            "model": config.model,
            "document": self._ocr_document(content, mime_type),
            "include_image_base64": False,
        }
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/ocr",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )
            return self._parse_ocr_response(response)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    @staticmethod
    def _ocr_document(content: bytes, mime_type: str) -> Dict[str, str]:
        """Build the Mistral OCR ``document`` payload from raw bytes (data-uri)."""
        mime = mime_type or "application/pdf"
        uri = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
        if mime.startswith("image/"):
            return {"type": "image_url", "image_url": uri}
        return {"type": "document_url", "document_url": uri}

    def _parse_ocr_response(self, response: httpx.Response) -> str:
        """Validate the OCR response and concatenate per-page markdown."""
        self._handle_error_status(response)
        data = response.json()
        pages = data.get("pages", [])
        return "\n\n".join(p.get("markdown", "") for p in pages).strip()

    # ========== Helpers ==========

    @staticmethod
    def _warn_if_non_stop_finish(ai_response: AIResponse, schema: Type[T]) -> None:
        """Log a warning when ``finish_reason`` indicates the response was not naturally stopped.

        ``stop`` means the model finished cleanly. Any other value (``length``, ``content_filter``,
        ``model_length``, ...) signals an unexpected interruption that may yield truncated or
        unsafe content even when Pydantic validation incidentally succeeds.
        """
        finish_reason = ai_response.finish_reason
        if not finish_reason or finish_reason == "stop":
            return
        completion_tokens = (ai_response.usage or {}).get("completion_tokens")
        logger.warning(
            "Mistral non-stop finish_reason for %s: finish_reason=%s, "
            "completion_tokens=%s, content_chars=%s",
            schema.__name__, finish_reason, completion_tokens, len(ai_response.content),
        )

    @staticmethod
    def _log_validation_failure(ai_response: AIResponse, schema: Type[T], error: Exception) -> None:
        """Log a warning when Pydantic validation fails on a Mistral structured response.

        Includes ``finish_reason``, ``completion_tokens`` and content length to help triage
        between truncation (``finish_reason=length``), schema mismatch (``finish_reason=stop``)
        and other interruptions. Caller is expected to raise ``AIValidationError`` afterward.
        """
        completion_tokens = (ai_response.usage or {}).get("completion_tokens")
        logger.warning(
            "Mistral response validation failed for %s: %s "
            "(finish_reason=%s, completion_tokens=%s, content_chars=%s)",
            schema.__name__, error, ai_response.finish_reason,
            completion_tokens, len(ai_response.content),
        )

    @staticmethod
    def _build_json_schema_response_format(schema: Type[T]) -> Dict[str, Any]:
        """Build the ``response_format`` payload for Mistral's native ``json_schema`` mode.

        The Pydantic-generated schema is sent as-is. ``strict`` is enabled so that the decoder
        enforces the schema constraint deterministically.

        Args:
            schema: Pydantic model class describing the expected response structure.

        Returns:
            A dict suitable for the Mistral chat completions ``response_format`` field.
        """
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        }

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
            finish_reason=choice.get("finish_reason"),
        )

    @classmethod
    def get_available_models(cls) -> List[str]:
        return cls.MODELS