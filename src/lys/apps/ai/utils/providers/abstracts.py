"""
AI provider abstract base class.

This module defines the abstract interface for AI providers,
allowing consistent usage across different LLM providers.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, List, Dict, Any, Optional, TypeVar, Type

from pydantic import BaseModel

from lys.apps.ai.utils.providers.config import AIEndpointConfig

T = TypeVar("T", bound=BaseModel)


@dataclass
class AIResponse:
    """Standardized response from any provider."""

    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, int]] = None  # tokens used
    model: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class AIStreamChunk:
    """A single chunk from a streaming AI response."""

    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    provider: Optional[str] = None


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    Each provider implements 4 methods:
    - chat / chat_sync: Standard text chat
    - chat_json / chat_json_sync: Structured JSON output with Pydantic validation

    Each provider handles JSON responses according to its API:
    - OpenAI: response_format with json_schema (strict)
    - Mistral: response_format with json_object + schema in prompt
    - Anthropic: tool_use with forced tool choice
    """

    name: str
    default_base_url: str

    # ========== Standard Chat ==========

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """
        Send a chat request to the provider.

        Args:
            messages: Conversation history
            config: Endpoint configuration
            tools: Optional tool definitions for function calling

        Returns:
            Standardized AIResponse

        Raises:
            AIAuthError: Invalid API key
            AIRateLimitError: Rate limit exceeded
            AIModelNotFoundError: Model not found
            AIProviderError: Provider-side error
            AITimeoutError: Request timed out
        """
        pass

    @abstractmethod
    def chat_sync(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Synchronous version for Celery workers."""
        pass

    # ========== Structured JSON Chat ==========

    @abstractmethod
    async def chat_json(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """
        Chat with structured JSON response validated against a Pydantic schema.

        Each provider implements this differently:
        - OpenAI: Uses response_format with json_schema (strict)
        - Mistral: Uses response_format json_object + schema in prompt
        - Anthropic: Uses tool_use with forced tool choice

        Args:
            messages: Conversation history
            config: Endpoint configuration
            schema: Pydantic model class for response validation

        Returns:
            Validated Pydantic model instance

        Raises:
            AIValidationError: Response doesn't match schema
            (plus all standard chat errors)
        """
        pass

    @abstractmethod
    def chat_json_sync(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous version for Celery workers."""
        pass

    # ========== Streaming ==========

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """
        Stream a chat response from the provider, yielding chunks as they arrive.

        Args:
            messages: Conversation history
            config: Endpoint configuration
            tools: Optional tool definitions for function calling

        Yields:
            AIStreamChunk for each SSE data line from the provider

        Raises:
            NotImplementedError: If the provider does not support streaming
        """
        raise NotImplementedError(f"{self.name} provider does not support streaming")
        # Make this an async generator
        yield  # pragma: no cover

    # ========== Helpers ==========

    def get_base_url(self, config: AIEndpointConfig) -> str:
        """Get base URL from config or default."""
        return config.base_url or self.default_base_url

    @classmethod
    def get_available_models(cls) -> List[str]:
        """Return list of known models for this provider."""
        return []

    def _inject_schema_in_messages(
        self,
        messages: List[Dict[str, Any]],
        schema: Type[BaseModel],
    ) -> List[Dict[str, Any]]:
        """
        Inject JSON schema description into system message.
        Used by providers that don't support native JSON schema (Mistral).
        """
        schema_prompt = f"""Respond with a JSON object matching this schema:
```json
{json.dumps(schema.model_json_schema(), indent=2)}
```
Return ONLY valid JSON, no additional text."""

        messages = messages.copy()

        if messages and messages[0]["role"] == "system":
            messages[0] = {
                "role": "system",
                "content": f"{messages[0]['content']}\n\n{schema_prompt}"
            }
        else:
            messages.insert(0, {"role": "system", "content": schema_prompt})

        return messages

    def _schema_to_tool(self, schema: Type[BaseModel]) -> Dict[str, Any]:
        """
        Convert Pydantic schema to tool definition.
        Used by Anthropic which uses tool_use for structured output.
        """
        return {
            "name": f"submit_{schema.__name__.lower()}",
            "description": f"Submit the structured {schema.__name__} response",
            "input_schema": schema.model_json_schema(),
        }