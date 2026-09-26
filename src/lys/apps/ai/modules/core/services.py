"""
AI Service with multi-provider support.

This module provides the main AIService class for interacting with
AI providers using purpose-based configuration, and AIToolService
for managing AI tool definitions.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import AsyncGenerator, List, Dict, Any, Optional, Type, TypeVar, TYPE_CHECKING

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from lys.apps.ai.modules.core.consts import AI_PLUGIN_NAME, ROUTES_MANIFEST_PURPOSE
from lys.apps.ai.utils.providers.abstracts import AIJsonResponse, AIProvider, AIResponse, AIStreamChunk
from lys.apps.ai.utils.providers.config import AIEndpointConfig, parse_plugin_config, AIConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIError,
    AIRateLimitError,
    AIProviderError,
    AIResponseTruncatedError,
    AIValidationError,
)
from lys.apps.ai.utils.message_sanitizer import sanitize_llm_messages
from lys.apps.ai.utils.schema_limits import find_fields_at_max_length
from lys.apps.ai.utils.providers.anthropic import AnthropicProvider
from lys.apps.ai.utils.providers.mistral import MistralProvider
from lys.core.consts.ai import ToolRiskLevel
from lys.core.graphql.client import GraphQLClient
from lys.core.registries import register_service
from lys.core.services import Service
from lys.core.utils.routes import load_routes_manifest
from lys.core.utils.strings import to_snake_case

if TYPE_CHECKING:
    from lys.apps.ai.modules.core.entities import AIPromptVersion

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


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

    # Prompt-version id per purpose, populated at boot by on_initialize (None when the
    # endpoint has no system_prompt). Settings are fixed for the process lifetime and
    # version rows are immutable, so the mapping never changes between boots — message
    # turns read it straight from memory instead of querying.
    _prompt_version_ids: Dict[str, Optional[str]] = {}

    # Cached routes manifest (loaded once from the chatbot config)
    _routes_manifest_cache: Optional[Dict[str, Any]] = None

    # Provider registry - can be overridden via inheritance
    _providers: Dict[str, Type[AIProvider]] = {
        "mistral": MistralProvider,
        "anthropic": AnthropicProvider,
    }

    # ========== Provider Registry ==========

    # ========== Routes Manifest ==========

    @classmethod
    def get_routes_manifest(cls) -> Optional[Dict[str, Any]]:
        """Get cached routes manifest, loading once if needed.

        Reads the ``routes_manifest_path`` from the chatbot endpoint's options.
        Returns an empty dict (not None) when no path is configured, so callers
        can iterate ``manifest.get("routes", [])`` without a None check.
        """
        if cls._routes_manifest_cache is not None:
            return cls._routes_manifest_cache

        ai_plugin_config = cls.app_manager.settings.get_plugin_config(AI_PLUGIN_NAME) or {}
        chatbot_config = ai_plugin_config.get("chatbot", {})
        routes_manifest_path = None
        if isinstance(chatbot_config, dict):
            routes_manifest_path = chatbot_config.get("options", {}).get("routes_manifest_path")

        if routes_manifest_path:
            cls._routes_manifest_cache = load_routes_manifest(routes_manifest_path)
        else:
            cls._routes_manifest_cache = {}

        return cls._routes_manifest_cache

    @classmethod
    def get_page_webservices(cls, page_name: str) -> set[str]:
        """Get webservices available on a specific page.

        Includes global webservices (always available) plus page-specific ones.
        Names are converted from camelCase (manifest) to snake_case (backend).
        """
        manifest = cls.get_routes_manifest()
        if not manifest:
            return set()

        global_webservices = {
            to_snake_case(ws) for ws in manifest.get("globalWebservices", [])
        }

        for route in manifest.get("routes", []):
            if route.get("name") == page_name:
                page_webservices = {
                    to_snake_case(ws) for ws in route.get("webservices", [])
                }
                return global_webservices | page_webservices

        return global_webservices

    @classmethod
    def get_page_chatbot_behaviour(cls, page_name: str) -> Optional[Dict[str, Any]]:
        """Get chatbot behaviour configuration for a specific page.

        Returns the ``chatbot_behaviour`` dict (with 'prompt', 'context_tools',
        'special_tools') or None if the page is not in the manifest.
        """
        manifest = cls.get_routes_manifest()
        if not manifest:
            return None

        for route in manifest.get("routes", []):
            if route.get("name") == page_name:
                return route.get("chatbot_behaviour")

        return None

    @classmethod
    def get_page_params_schema(cls, page_name: str) -> Optional[Dict[str, Any]]:
        """Get the declared URL params of a page, or None when it declares none.

        The declaration is the boundary that makes client-supplied params readable by
        the model: only what it covers is rendered into the prompt (see
        ``validate_page_params``). It lives in the routes manifest — server-side and
        versioned — so the client cannot widen it.

        Returns the route's ``params`` dict, mapping each param name to its spec
        (``{"type": ..., ...}``).
        """
        manifest = cls.get_routes_manifest()
        if not manifest:
            return None

        for route in manifest.get("routes", []):
            if route.get("name") == page_name:
                params_schema = route.get("params")
                return params_schema if isinstance(params_schema, dict) else None

        return None

    # ========== Prompt Versioning ==========

    @classmethod
    async def on_initialize(cls) -> None:
        """Version configured system prompts, prompt segments and the routes manifest.

        Three sources are versioned into ``ai_prompt_version``:

        1. **Endpoint prompts** — each endpoint's ``system_prompt`` from the AI
           plugin config, keyed by ``purpose`` (e.g. "chatbot", "analysis").
        2. **Prompt segments** — config keys of an endpoint declared by the
           consumer under ``prompt_segments`` (e.g. the conversation segment
           headers ``summary_header`` / ``dynamic_context_header``), keyed by
           ``"<purpose>:<key>"``. The consumer declares what is prompt text;
           tuning keys (options, compaction) never appear there.
        3. **The routes manifest** — the whole document, registered with its
           hash as a single row under ``ROUTES_MANIFEST_PURPOSE``. The page
           prompts it carries are part of the document: any change to one of
           them creates a new manifest version.

        A version already known (same hash) is not re-registered. Fault-tolerant
        per entry: a failure on one does not prevent the others, and the whole
        hook never aborts startup (errors are logged).

        The concurrent boot race (multiple processes booting in parallel) is
        handled by the unique constraint on ``(purpose, hash)`` inside a
        SAVEPOINT — same pattern as ``LegalDocumentVersionService.publish``.
        """
        try:
            config = cls.get_config()
        except ValueError:
            logger.warning("AIService: AI plugin not configured, skipping prompt versioning")
            return

        for purpose, endpoint in config.endpoints.items():
            if not endpoint.system_prompt:
                cls._prompt_version_ids[purpose] = None
            else:
                version = await cls._version_prompt(purpose, endpoint.system_prompt)
                if version is not None:
                    cls._prompt_version_ids[purpose] = version.id

            await cls._version_prompt_segments(purpose)

        # The routes manifest — one version row for the whole document. Serialized
        # with sorted keys so the hash is stable across boots and processes.
        manifest = cls.get_routes_manifest()
        if not manifest:
            return

        try:
            async with cls.app_manager.database.get_session() as session:
                await cls._upsert_prompt_version(
                    ROUTES_MANIFEST_PURPOSE,
                    json.dumps(manifest, sort_keys=True),
                    session=session,
                )
        except Exception as exc:
            logger.error("AIService: failed to version the routes manifest: %s", exc)

    @classmethod
    def _get_endpoint_raw_config(cls, purpose: str) -> Dict[str, Any]:
        """The raw plugin-config dict of an endpoint, or an empty dict when absent or malformed."""
        plugin_config = cls.app_manager.settings.get_plugin_config(AI_PLUGIN_NAME) or {}
        raw = plugin_config.get(purpose)
        return raw if isinstance(raw, dict) else {}

    @classmethod
    async def _version_prompt(cls, purpose: str, content: str) -> Optional["AIPromptVersion"]:
        """Version one prompt in its own session; log and return None on failure."""
        try:
            async with cls.app_manager.database.get_session() as session:
                return await cls._upsert_prompt_version(purpose, content, session=session)
        except Exception as exc:
            logger.error("AIService: failed to version prompt for purpose '%s': %s", purpose, exc)
            return None

    @classmethod
    async def _version_prompt_segments(cls, purpose: str) -> None:
        """Version the prompt segments an endpoint declares under ``prompt_segments``.

        A malformed declaration or a declared key that is missing (typo, removal) or
        not a string warns at boot rather than silently versioning nothing.
        """
        raw = cls._get_endpoint_raw_config(purpose)
        declared = raw.get("prompt_segments")
        if declared is None:
            return
        if not isinstance(declared, (list, tuple)):
            logger.warning(
                "AIService: 'prompt_segments' for purpose '%s' must be a list of keys — ignored", purpose
            )
            return

        for key in declared:
            value = raw.get(key)
            if not isinstance(value, str) or not value:
                logger.warning(
                    "AIService: prompt segment '%s' declared for purpose '%s' but "
                    "missing or not a string — not versioned", key, purpose,
                )
                continue
            await cls._version_prompt(f"{purpose}:{key}", value)

    @classmethod
    async def _upsert_prompt_version(
        cls,
        purpose: str,
        content: str,
        *,
        session,
    ) -> "AIPromptVersion":
        """Idempotently insert a prompt version row.

        Checks by hash first; on a concurrent insert the unique constraint fires
        inside a SAVEPOINT and the winning row is returned.
        """
        entity = cls.app_manager.get_entity("ai_prompt_version")
        prompt_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing_stmt = select(entity).where(
            entity.purpose == purpose,
            entity.hash == prompt_hash,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        instance = entity(
            purpose=purpose,
            content=content,
            hash=prompt_hash,
        )
        try:
            async with session.begin_nested():
                session.add(instance)
        except IntegrityError:
            return (await session.execute(existing_stmt)).scalar_one()
        return instance

    @classmethod
    def get_prompt_version_id(cls, purpose: str) -> Optional[str]:
        """The id of the prompt version in force for a purpose, from the boot cache.

        Best-effort by contract: None when the purpose has no endpoint, no system
        prompt, or its version could not be registered at boot — the caller then
        leaves the FK unset rather than failing the turn.
        """
        return cls._prompt_version_ids.get(purpose)

    @classmethod
    def get_prompt_segment(cls, purpose: str, key: str) -> Optional[str]:
        """A prompt segment declared on an endpoint's config (see ``prompt_segments``).

        Returns None when the purpose, the key or the value is absent or not a
        string — the caller decides whether that is fatal for its use.
        """
        value = cls._get_endpoint_raw_config(purpose).get(key)
        return value if isinstance(value, str) else None

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
        """Clear the config cache to force reload.

        Also clears the boot-time prompt-version cache: it is derived from the
        config (a reloaded config may carry different prompts), and re-populating
        it is on_initialize's job, not the request path's.
        """
        cls._config_cache = None
        cls._prompt_version_ids = {}

    # ========== Purpose-based Chat (convenience) ==========

    @classmethod
    async def chat_with_purpose(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        cache_key: Optional[str] = None,
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
        if cache_key:
            config = config.with_cache_key(cache_key)
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

    @classmethod
    async def chat_stream_with_purpose(
        cls,
        messages: List[Dict[str, Any]],
        purpose: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        cache_key: Optional[str] = None,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """
        Stream a chat response using a configured purpose.

        Tries the primary provider, falls back on connection error (no retry mid-stream).

        Args:
            messages: Conversation messages
            purpose: Purpose name (e.g., "chatbot")
            tools: Optional tool definitions

        Yields:
            AIStreamChunk for each piece of the response
        """
        endpoint = cls.get_endpoint(purpose)
        if cache_key:
            endpoint = endpoint.with_cache_key(cache_key)

        if endpoint.system_prompt:
            messages = [{"role": "system", "content": endpoint.system_prompt}] + messages
        messages = sanitize_llm_messages(messages)

        current_endpoint = endpoint
        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)
            try:
                async for chunk in provider.chat_stream(messages, current_endpoint, tools):
                    yield chunk
                return
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                logger.warning(f"Connection error on {current_endpoint.provider}: {e}")
                current_endpoint = current_endpoint.fallback
                if current_endpoint:
                    logger.info(f"Falling back to {current_endpoint.provider}/{current_endpoint.model}")
            except AIError:
                raise

        raise AIError("All providers failed for streaming")

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
            AIError: No endpoint in the fallback chain succeeded. The message carries
                the last provider error, also chained as ``__cause__``.
        """
        # Add system prompt from config if present
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages
        messages = sanitize_llm_messages(messages)

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
        messages = sanitize_llm_messages(messages)

        return cls._chat_with_fallback_sync(messages, config, tools)

    # ========== Embeddings ==========

    @classmethod
    async def embed_with_purpose(cls, texts: List[str], purpose: str) -> List[List[float]]:
        """
        Embed texts using a configured purpose.

        No fallback chain, unlike chat: two providers do not embed into the same space, so
        silently answering with a second one would return vectors that cannot be compared
        with those already stored. A failure here has to surface.

        Args:
            texts: Texts to embed, in one call.
            purpose: Purpose name (e.g. "embedding").

        Returns:
            One vector per input text, in the same order.
        """
        config = cls.get_endpoint(purpose)
        return await cls.get_provider(config.provider).embed(texts, config)

    @classmethod
    def embed_with_purpose_sync(cls, texts: List[str], purpose: str) -> List[List[float]]:
        """Synchronous version for Celery workers."""
        config = cls.get_endpoint(purpose)
        return cls.get_provider(config.provider).embed_sync(texts, config)

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
            AIError: No endpoint in the fallback chain produced a valid response.
                The message carries the last provider error (schema mismatch,
                truncation, rate limit, ...), which is also chained as ``__cause__``.
        """
        return (await cls.chat_json_with_metadata(messages, config, schema)).data

    @classmethod
    def chat_json_sync(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous version for Celery workers."""
        return cls.chat_json_with_metadata_sync(messages, config, schema).data

    @classmethod
    async def chat_json_with_metadata(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> AIJsonResponse[T]:
        """
        Same as ``chat_json``, but also returns the endpoint that produced the response.

        Use it when the caller stores which model authored a result: after a fallback,
        ``config.model`` names the primary endpoint, not the one that answered.

        Raises:
            AIError: No endpoint in the fallback chain produced a valid response.
        """
        messages = cls._prepare_json_messages(messages, config)
        return await cls._chat_json_with_fallback(messages, config, schema)

    @classmethod
    def chat_json_with_metadata_sync(
        cls,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> AIJsonResponse[T]:
        """Synchronous version of ``chat_json_with_metadata`` for Celery workers."""
        messages = cls._prepare_json_messages(messages, config)
        return cls._chat_json_with_fallback_sync(messages, config, schema)

    @staticmethod
    def _prepare_json_messages(
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
    ) -> List[Dict[str, Any]]:
        """Prepend the endpoint system prompt and sanitize the conversation."""
        if config.system_prompt:
            messages = [{"role": "system", "content": config.system_prompt}] + messages
        return sanitize_llm_messages(messages)

    @staticmethod
    def _raise_if_capped(data: Any, endpoint: AIEndpointConfig) -> None:
        """
        Reject a structured response whose text fields reached their schema ``maxLength``.

        Constrained decoding cuts such a field mid-word while the JSON stays valid; the
        cut is raised as a truncation so the chain falls back instead of returning it.
        """
        if not isinstance(data, BaseModel):
            return
        capped = find_fields_at_max_length(data)
        if capped:
            raise AIResponseTruncatedError(
                f"{endpoint.provider}/{endpoint.model} reached maxLength on: {', '.join(capped)}"
            )

    # ========== OCR ==========

    @classmethod
    async def ocr(
        cls,
        content: bytes,
        mime_type: str,
        config: AIEndpointConfig,
    ) -> str:
        """
        Extract a document's textual content via OCR, returning markdown.

        Walks the fallback chain: if a provider does not support OCR
        (NotImplementedError) or errors, the next endpoint is tried.

        Args:
            content: Raw document bytes (PDF or image).
            mime_type: MIME type of the document.
            config: Endpoint configuration (e.g. from ``get_endpoint("ocr")``).

        Returns:
            Concatenated markdown of all pages.

        Raises:
            AIError: No provider in the chain succeeded.
        """
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            try:
                return await provider.ocr(content, mime_type, current)
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support OCR; trying fallback")
            except AIError as e:
                last_error = e
                logger.error(f"OCR failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"OCR failed: no provider in the chain succeeded ({last_error})")

    @classmethod
    def ocr_sync(
        cls,
        content: bytes,
        mime_type: str,
        config: AIEndpointConfig,
    ) -> str:
        """Synchronous version of :meth:`ocr` for Celery workers."""
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            try:
                return provider.ocr_sync(content, mime_type, current)
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support OCR; trying fallback")
            except AIError as e:
                last_error = e
                logger.error(f"OCR failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"OCR failed: no provider in the chain succeeded ({last_error})")

    # ========== Transcription ==========

    @classmethod
    async def transcribe(
        cls,
        content: bytes,
        filename: str,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe speech audio into text.

        Walks the fallback chain: if a provider does not support transcription
        (NotImplementedError) or errors, the next endpoint is tried.

        Args:
            content: Raw audio bytes (e.g. MP3, WAV, OGG).
            filename: File name carrying the audio extension.
            config: Endpoint configuration (e.g. from ``get_endpoint("transcription")``).
            language: Optional ISO language code (e.g. "fr") when already known.

        Returns:
            The transcribed text.

        Raises:
            AIError: No provider in the chain succeeded.
        """
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            try:
                return await provider.transcribe(content, filename, current, language)
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support transcription; trying fallback")
            except AIError as e:
                last_error = e
                logger.error(f"Transcription failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"Transcription failed: no provider in the chain succeeded ({last_error})")

    @classmethod
    def transcribe_sync(
        cls,
        content: bytes,
        filename: str,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> str:
        """Synchronous version of :meth:`transcribe` for Celery workers."""
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            try:
                return provider.transcribe_sync(content, filename, current, language)
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support transcription; trying fallback")
            except AIError as e:
                last_error = e
                logger.error(f"Transcription failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"Transcription failed: no provider in the chain succeeded ({last_error})")

    # ========== Synthesis (text-to-speech) ==========

    @classmethod
    async def synthesize(
        cls,
        text: str,
        config: AIEndpointConfig,
        voice: str,
        response_format: str = "mp3",
    ) -> bytes:
        """
        Synthesize text into speech audio.

        Walks the fallback chain: if a provider does not support synthesis
        (NotImplementedError) or errors, the next endpoint is tried.

        Args:
            text: The text to speak.
            config: Endpoint configuration (e.g. from ``get_endpoint("tts")``).
            voice: Voice identifier — the provider API has no default, so the
                caller resolves one (endpoint ``options["voice"]`` unless the
                request overrides it).
            response_format: Audio container ("mp3", "wav", "flac", "opus").

        Returns:
            The audio bytes in the requested format.

        Raises:
            AIError: No provider in the chain succeeded.
        """
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            try:
                return await provider.synthesize(text, current, voice, response_format)
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support synthesis; trying fallback")
            except AIError as e:
                last_error = e
                logger.error(f"Synthesis failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"Synthesis failed: no provider in the chain succeeded ({last_error})")

    @classmethod
    def synthesize_sync(
        cls,
        text: str,
        config: AIEndpointConfig,
        voice: str,
        response_format: str = "mp3",
    ) -> bytes:
        """Synchronous version of :meth:`synthesize` for Celery workers."""
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            try:
                return provider.synthesize_sync(text, current, voice, response_format)
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support synthesis; trying fallback")
            except AIError as e:
                last_error = e
                logger.error(f"Synthesis failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"Synthesis failed: no provider in the chain succeeded ({last_error})")

    @classmethod
    async def synthesize_stream(
        cls,
        text: str,
        config: AIEndpointConfig,
        voice: str,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech synthesis as raw PCM audio chunks.

        Walks the fallback chain with one streaming-specific rule: a provider
        that fails AFTER the first chunk was yielded is not retried — the
        caller has already played that audio, and silently restarting the
        sentence on another voice would splice two voices mid-word. Only a
        provider that fails before producing anything falls through.

        Args:
            text: The text to speak.
            config: Endpoint configuration (e.g. from ``get_endpoint("tts")``).
            voice: Voice identifier — the provider API has no default, so the
                caller resolves one (endpoint ``options["voice"]`` unless the
                request overrides it).

        Yields:
            Raw PCM audio bytes, in generation order.

        Raises:
            AIError: No provider in the chain succeeded.
        """
        current: Optional[AIEndpointConfig] = config
        last_error: Optional[Exception] = None
        while current is not None:
            provider = cls.get_provider(current.provider)
            emitted = False
            try:
                async for chunk in provider.synthesize_stream(text, current, voice):
                    emitted = True
                    yield chunk
                return
            except NotImplementedError as e:
                last_error = e
                logger.warning(f"Provider '{current.provider}' does not support streaming synthesis; trying fallback")
            except AIError as e:
                if emitted:
                    # Mid-stream failure: audio already left this generator.
                    raise
                last_error = e
                logger.error(f"Streaming synthesis failed on '{current.provider}': {e}")
            current = current.fallback
        raise AIError(f"Streaming synthesis failed: no provider in the chain succeeded ({last_error})")

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
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return await provider.chat(messages, current_endpoint, tools)

                except AIRateLimitError as e:
                    # Rate limit → try fallback immediately
                    logger.warning(
                        f"Rate limit on {current_endpoint.provider}, trying fallback"
                    )
                    last_error = e
                    break

                except AIProviderError as e:
                    # Server error → retry
                    last_error = e
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

                except AIError as e:
                    # Other AI errors → don't retry, try fallback
                    last_error = e
                    break

            # Try fallback if configured
            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}"
                )

        if last_error:
            logger.error(f"All providers failed: {last_error}")
            raise AIError(f"All providers failed: {last_error}") from last_error
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
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    return provider.chat_sync(messages, current_endpoint, tools)

                except AIRateLimitError as e:
                    last_error = e
                    break

                except AIProviderError as e:
                    last_error = e
                    if retry < cls.MAX_RETRIES - 1:
                        time.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        break

                except AIError as e:
                    last_error = e
                    break

            current_endpoint = current_endpoint.fallback

        if last_error:
            logger.error(f"All providers failed: {last_error}")
            raise AIError(f"All providers failed: {last_error}") from last_error
        raise AIError("All providers failed")

    @classmethod
    async def _chat_json_with_fallback(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        schema: Type[T],
    ) -> AIJsonResponse[T]:
        """Retry and fallback logic for chat_json, keeping track of the answering endpoint."""
        current_endpoint = endpoint
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    data = await provider.chat_json(messages, current_endpoint, schema)
                    cls._raise_if_capped(data, current_endpoint)
                    return AIJsonResponse(
                        data=data,
                        model=current_endpoint.model,
                        provider=current_endpoint.provider,
                    )

                except AIRateLimitError as e:
                    logger.warning(
                        f"Rate limit on {current_endpoint.provider}, trying fallback"
                    )
                    last_error = e
                    break

                except AIResponseTruncatedError as e:
                    # Truncation is deterministic: retrying the same endpoint hits the
                    # same output limit. Fall back instead.
                    logger.warning(
                        f"Truncated response on {current_endpoint.provider}, trying fallback"
                    )
                    last_error = e
                    break

                except (AIProviderError, AIValidationError) as e:
                    # A schema violation is usually a one-off formatting glitch: retry on
                    # the same endpoint before falling back.
                    last_error = e
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

                except AIError as e:
                    last_error = e
                    break

            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}"
                )

        if last_error:
            logger.error(f"All providers failed: {last_error}")
            raise AIError(f"All providers failed: {last_error}") from last_error
        raise AIError("All providers failed")

    @classmethod
    def _chat_json_with_fallback_sync(
        cls,
        messages: List[Dict[str, Any]],
        endpoint: AIEndpointConfig,
        schema: Type[T],
    ) -> AIJsonResponse[T]:
        """Synchronous twin of ``_chat_json_with_fallback``."""
        current_endpoint = endpoint
        last_error: Optional[Exception] = None

        while current_endpoint is not None:
            provider = cls.get_provider(current_endpoint.provider)

            for retry in range(cls.MAX_RETRIES):
                try:
                    data = provider.chat_json_sync(messages, current_endpoint, schema)
                    cls._raise_if_capped(data, current_endpoint)
                    return AIJsonResponse(
                        data=data,
                        model=current_endpoint.model,
                        provider=current_endpoint.provider,
                    )

                except AIRateLimitError as e:
                    last_error = e
                    break

                except AIResponseTruncatedError as e:
                    # See the async twin: truncation falls back without retrying.
                    last_error = e
                    break

                except (AIProviderError, AIValidationError) as e:
                    last_error = e
                    if retry < cls.MAX_RETRIES - 1:
                        time.sleep(cls.RETRY_DELAY * (retry + 1))
                    else:
                        break

                except AIError as e:
                    last_error = e
                    break

            current_endpoint = current_endpoint.fallback
            if current_endpoint:
                logger.info(
                    f"Falling back to {current_endpoint.provider}/{current_endpoint.model}: {last_error}"
                )

        if last_error:
            logger.error(f"All providers failed: {last_error}")
            raise AIError(f"All providers failed: {last_error}") from last_error
        raise AIError("All providers failed")


@register_service()
class AIToolService(Service):
    """
    Service for managing AI tool definitions.

    This service provides:
    - Fetches tools from Apollo Gateway via GraphQL
    - JWT-based filtering for accessible tools
    - Lazy loading with caching

    Configuration via executor config in AI plugin:
        settings.configure_plugin("ai",
            executor={
                "gateway_url": "http://localhost:8000/graphql",
                "service_name": "my-api",
            },
        )

    Usage:
        ai_tool_service = app_manager.get_service("ai_tool")
        tools = await ai_tool_service.get_accessible_tools(connected_user)
    """

    service_name = "ai_tool"

    # Cached tools with resolvers and metadata
    _tools: Dict[str, Dict[str, Any]] = {}
    _initialized: bool = False

    @classmethod
    async def get_accessible_tools(cls, connected_user: Dict[str, Any]) -> List[Dict]:
        """
        Get tool definitions filtered by JWT claims.

        For super_users, all tools are returned without filtering because:
        - The permission layer grants super_users access to everything
        - JWT claims don't contain all webservices for super_users (by design)
        - See AuthService.generate_access_claims() for the JWT override chain

        For regular users, tools are filtered based on:
        - "webservices" claim: global webservices (PUBLIC, CONNECTED, OWNER, ROLE)
        - "organizations" claim: per-organization webservices (ORGANIZATION_ROLE)

        Args:
            connected_user: Connected user dict from context, containing:
                            - "webservices": dict of accessible webservice names
                            - "organizations": dict of per-org webservices (client owners, client_user roles)
                            - "is_super_user": boolean

        Returns:
            List of tool definitions for LLM function calling
        """
        if not cls._initialized:
            await cls._load_tools()

        # Super users get all tools - permission layer handles actual access control
        is_super_user = connected_user.get("is_super_user", False) if connected_user else False
        if is_super_user:
            return [
                {
                    "webservice": name,
                    "definition": tool_data["definition"],
                    "operation_type": tool_data.get("operation_type"),
                }
                for name, tool_data in cls._tools.items()
            ]

        # Regular users: collect all accessible webservices from JWT claims
        accessible_ids = set()

        # Add global webservices (PUBLIC, CONNECTED, OWNER, ROLE access levels)
        jwt_webservices = connected_user.get("webservices", {}) if connected_user else {}
        accessible_ids.update(jwt_webservices.keys())

        # Add organization-scoped webservices (ORGANIZATION_ROLE access level)
        # This includes client owners and users with client_user_roles
        organizations = connected_user.get("organizations", {}) if connected_user else {}
        for org_data in organizations.values():
            org_webservices = org_data.get("webservices", [])
            accessible_ids.update(org_webservices)

        return [
            {
                "webservice": name,
                "definition": tool_data["definition"],
                "operation_type": tool_data.get("operation_type"),
            }
            for name, tool_data in cls._tools.items()
            if name in accessible_ids
        ]

    @classmethod
    async def get_tool(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific tool by name.

        Args:
            name: Tool name to lookup

        Returns:
            Tool data dict with definition, resolver, node_type, etc.
            None if tool not found.
        """
        if not cls._initialized:
            await cls._load_tools()

        return cls._tools.get(name)

    @classmethod
    async def _load_tools(cls):
        """Load tools from Apollo Gateway via GraphQL."""
        config = cls.app_manager.settings.get_plugin_config(AI_PLUGIN_NAME)
        if not config:
            logger.warning("AI plugin not configured, no tools loaded")
            cls._initialized = True
            return

        executor_config = config.get("executor", {})
        await cls._load_tools_remote(executor_config)

        cls._initialized = True
        logger.debug(f"AIToolService loaded {len(cls._tools)} tools from gateway: {list(cls._tools.keys())}")

    @classmethod
    async def _load_tools_remote(cls, executor_config: Dict[str, Any]):
        """Fetch tools from GraphQL endpoint."""
        gateway_url = executor_config.get("gateway_url")
        service_name = executor_config.get("service_name")
        secret_key = cls.app_manager.settings.secret_key
        timeout = executor_config.get("timeout", 30)
        verify_ssl = executor_config.get("verify_ssl", True)

        if not gateway_url:
            logger.error("gateway_url not configured for graphql mode")
            return

        client = GraphQLClient(
            url=gateway_url,
            secret_key=secret_key,
            service_name=service_name or "ai-service",
            timeout=timeout,
            verify_ssl=verify_ssl,
        )

        query = """
        query GetAITools {
            allWebservices(isAiTool: true) {
                edges {
                    node {
                        id
                        code
                        operationType
                        aiTool
                    }
                }
            }
        }
        """

        try:
            data = await client.execute(query)

            if "errors" in data:
                logger.error(f"GraphQL errors fetching tools: {data['errors']}")
                return

            edges = data.get("data", {}).get("allWebservices", {}).get("edges", [])
            for edge in edges:
                node = edge.get("node", {})
                ai_tool = node.get("aiTool")
                if ai_tool:
                    name = ai_tool.get("function", {}).get("name") or node.get("code")
                    cls._tools[name] = {
                        "definition": ai_tool,
                        "resolver": None,  # No resolver in graphql mode
                        "node_type": None,
                        "operation_type": node.get("operationType") or "mutation",
                        "risk_level": ToolRiskLevel.READ,  # Default, could be fetched
                        "confirmation_fields": [],
                    }

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch tools from gateway: {e}")

    @classmethod
    def reset(cls):
        """Reset the service state. Useful for testing."""
        cls._tools = {}
        cls._initialized = False


@register_service()
class ContextToolService(Service):
    """
    Service for managing context tools used by chatbot page behaviours.

    This service provides a registry for context tools that can be called
    dynamically based on the page's `context_tools` configuration in the
    routes manifest.

    Services register their context tool functions during initialization:

        class ContextualQuestionService(EntityService):
            @classmethod
            async def on_initialize(cls):
                context_tool_service = cls.app_manager.get_service("context_tool")
                context_tool_service.register(
                    "get_contextual_questions",
                    cls.get_for_prompt
                )

    Then AIConversationService can execute tools dynamically:

        results = await context_tool_service.execute_all(
            context_tools={"questions": "get_contextual_questions"},
            session=session,
            access_token=access_token,
            **page_params,
        )

    Usage:
        context_tool_service = app_manager.get_service("context_tool")
        context_tool_service.register("get_contextual_questions", my_func)
        result = await context_tool_service.execute("get_contextual_questions", ...)
    """

    service_name = "context_tool"

    # Registry mapping function names to callables
    _registry: Dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, func: Any) -> None:
        """
        Register a context tool function.

        Args:
            name: Function name as referenced in routes manifest context_tools
            func: Async callable returning str. It receives ``session`` and ``access_token``
                plus the page params as keyword arguments, so it accepts ``**kwargs`` and
                reads only the keys it needs - the framework does not fix that set.
        """
        cls._registry[name] = func
        logger.info(f"ContextToolService: registered '{name}'")

    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """
        Get a registered context tool function.

        Args:
            name: Function name to lookup

        Returns:
            The registered callable or None if not found
        """
        return cls._registry.get(name)

    @classmethod
    async def execute(
        cls,
        name: str,
        session: Any,
        access_token: str,
        **params,
    ) -> Optional[str]:
        """
        Execute a registered context tool.

        Args:
            name: Function name to execute
            session: Database session
            access_token: User's JWT access token for authenticated GraphQL calls
            **params: Parameters to pass to the function

        Returns:
            Result string from the function, or None if function not found
        """
        func = cls._registry.get(name)
        if not func:
            logger.warning(f"ContextToolService: unknown function '{name}'")
            return None

        try:
            return await func(session=session, access_token=access_token, **params)
        except Exception as e:
            logger.error(f"ContextToolService: error executing '{name}': {e}")
            return None

    @classmethod
    async def execute_all(
        cls,
        context_tools: Dict[str, str],
        session: Any,
        access_token: str,
        **params,
    ) -> Dict[str, str]:
        """
        Execute all context tools and return results.

        Args:
            context_tools: Dict mapping labels to function names
                e.g., {"contextual_questions": "get_contextual_questions"}
            session: Database session
            access_token: User's JWT access token for authenticated GraphQL calls
            **params: Parameters to pass to functions

        Returns:
            Dict mapping labels to result strings (only for successful calls)
        """
        results = {}

        for label, function_name in context_tools.items():
            result = await cls.execute(function_name, session, access_token, **params)
            if result:
                results[label] = result

        return results

    @classmethod
    def reset(cls):
        """Reset the registry. Useful for testing."""
        cls._registry = {}