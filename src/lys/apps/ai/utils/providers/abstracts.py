"""
AI provider abstract base class.

This module defines the abstract interface for AI providers,
allowing consistent usage across different LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, List, Dict, Any, Generic, Optional, Sequence, TypeVar, Type

from pydantic import BaseModel

from lys.apps.ai.utils.providers.config import AIEndpointConfig

T = TypeVar("T", bound=BaseModel)

# finish_reason values meaning the provider stopped on the output token limit.
# "model_length" is Mistral-specific; Anthropic's "max_tokens" is mapped to "length".
TRUNCATION_FINISH_REASONS = frozenset({"length", "model_length"})


@dataclass
class AIResponse:
    """Standardized response from any provider."""

    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, int]] = None  # tokens used
    model: Optional[str] = None
    provider: Optional[str] = None
    finish_reason: Optional[str] = None  # "stop" | "length" | "tool_calls" | ...


@dataclass
class AIJsonResponse(Generic[T]):
    """
    Validated structured response, tagged with the endpoint that actually produced it.

    When the fallback chain was walked, ``model`` and ``provider`` name the fallback
    endpoint, not the primary one the caller configured.
    """

    data: T
    model: str
    provider: str


@dataclass
class AIStreamChunk:
    """A single chunk from a streaming AI response."""

    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    # Reasoning trace emitted by thinking models, kept apart from ``content`` so it never
    # reaches the user by accident. Optional and unset by default: consumers that ignore it
    # behave exactly as before. It arrives long before the answer (~1 s versus ~30 s on
    # mistral-medium-3-5 with reasoning_effort=high), which makes it the only live signal
    # available during that gap.
    reasoning: Optional[str] = None


class AIBatchState(str, Enum):
    """
    Where a batch job stands, in provider-neutral terms.

    Only COMPLETED guarantees every request was processed. A job that EXPIRED (its
    timeout passed first), FAILED or was CANCELLED may hold results for part of its
    requests: the ones missing from its results were not processed.
    """

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

    @property
    def is_final(self) -> bool:
        """Whether the job will not move any more: its results can be read."""
        return self is not AIBatchState.PENDING


@dataclass(frozen=True)
class AIBatchRequest:
    """
    One request of a batch job.

    ``custom_id`` is the caller's key for the request, returned with its result: it
    must be unique within the job. ``messages`` are sent as they are to a chat call.
    """

    custom_id: str
    messages: List[Dict[str, Any]]


@dataclass(frozen=True)
class AIBatchJob:
    """A batch job as the provider last reported it."""

    id: str
    state: AIBatchState
    provider: str
    model: str
    total_requests: int = 0
    succeeded_requests: int = 0
    failed_requests: int = 0


@dataclass(frozen=True)
class AIBatchResult(Generic[T]):
    """
    The outcome of one request of a batch job: its validated ``data``, or the
    ``error`` that prevented it — never both. ``usage`` is the provider's token
    count for the request, when it reports one.
    """

    custom_id: str
    data: Optional[T] = None
    error: Optional[Exception] = None
    usage: Optional[Dict[str, Any]] = None


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    Each provider implements 4 methods:
    - chat / chat_sync: Standard text chat
    - chat_json / chat_json_sync: Structured JSON output with Pydantic validation

    Each provider handles JSON responses according to its API:
    - OpenAI: response_format with json_schema (strict)
    - Mistral: response_format with json_schema (strict)
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
        tool_calls_allowed: bool = True,
    ) -> AIResponse:
        """
        Send a chat request to the provider.

        Args:
            messages: Conversation history
            config: Endpoint configuration
            tools: Optional tool definitions for function calling
            tool_calls_allowed: False to require a text answer: the tools stay declared (a
                history holding tool calls needs them on some providers) but the model
                may not call one

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
        - Mistral: Uses response_format with json_schema (strict)
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
        tool_calls_allowed: bool = True,
    ) -> AsyncGenerator[AIStreamChunk, None]:
        """
        Stream a chat response from the provider, yielding chunks as they arrive.

        Args:
            messages: Conversation history
            config: Endpoint configuration
            tools: Optional tool definitions for function calling
            tool_calls_allowed: False to require a text answer: the tools stay declared (a
                history holding tool calls needs them on some providers) but the model
                may not call one

        Yields:
            AIStreamChunk for each SSE data line from the provider

        Raises:
            NotImplementedError: If the provider does not support streaming
        """
        raise NotImplementedError(f"{self.name} provider does not support streaming")
        # Make this an async generator
        yield  # pragma: no cover

    # ========== OCR ==========

    async def ocr(
        self,
        content: bytes,
        mime_type: str,
        config: AIEndpointConfig,
    ) -> str:
        """
        Extract a document's textual content via OCR, returning markdown.

        Optional capability: providers that do not support OCR raise
        NotImplementedError so the service can fall back to another provider.

        Args:
            content: Raw document bytes (PDF or image).
            mime_type: MIME type of the document (e.g. "application/pdf", "image/png").
            config: Endpoint configuration (carries api_key, base_url, model).

        Returns:
            Concatenated markdown of all pages.

        Raises:
            NotImplementedError: If the provider does not support OCR.
        """
        raise NotImplementedError(f"{self.name} provider does not support OCR")

    def ocr_sync(
        self,
        content: bytes,
        mime_type: str,
        config: AIEndpointConfig,
    ) -> str:
        """Synchronous version of :meth:`ocr` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support OCR")

    # ========== Embeddings ==========

    async def embed(
        self,
        texts: List[str],
        config: AIEndpointConfig,
    ) -> List[List[float]]:
        """
        Turn texts into embedding vectors.

        Optional capability, like OCR: a provider that does not embed raises
        NotImplementedError rather than returning something empty, so a caller can tell
        "this provider cannot" from "this text has no vector".

        Args:
            texts: Texts to embed, in one call - providers bill and rate-limit per
                request, so batching is the caller's lever.
            config: Endpoint configuration (carries api_key, base_url, model).

        Returns:
            One vector per input text, in the same order.

        Raises:
            NotImplementedError: If the provider does not support embeddings.
        """
        raise NotImplementedError(f"{self.name} provider does not support embeddings")

    def embed_sync(
        self,
        texts: List[str],
        config: AIEndpointConfig,
    ) -> List[List[float]]:
        """Synchronous version of :meth:`embed` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support embeddings")

    # ========== Transcription ==========

    async def transcribe(
        self,
        content: bytes,
        filename: str,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> str:
        """
        Transcribe speech audio into text.

        Optional capability, like OCR and embeddings: a provider that does not
        transcribe raises NotImplementedError rather than returning something
        empty, so a caller can tell "this provider cannot" from "this audio has
        no speech".

        Args:
            content: Raw audio bytes (e.g. MP3, WAV, OGG).
            filename: File name carrying the audio extension; providers derive
                the upload part name and content type from it.
            config: Endpoint configuration (carries api_key, base_url, model).
            language: Optional ISO language code (e.g. "fr") when the language
                is already known — improves accuracy over detection.

        Returns:
            The transcribed text.

        Raises:
            NotImplementedError: If the provider does not support transcription.
        """
        raise NotImplementedError(f"{self.name} provider does not support transcription")

    def transcribe_sync(
        self,
        content: bytes,
        filename: str,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> str:
        """Synchronous version of :meth:`transcribe` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support transcription")

    # ========== Synthesis (text-to-speech) ==========

    async def synthesize(
        self,
        text: str,
        config: AIEndpointConfig,
        voice: str,
        response_format: str = "mp3",
    ) -> bytes:
        """
        Synthesize text into speech audio.

        Optional capability, like transcription: a provider that does not
        synthesize raises NotImplementedError, so a caller can tell "this
        provider cannot" from "this text has no audio".

        ``voice`` is explicit rather than defaulted: the Mistral speech API
        rejects a request without one ("Either ref_audio or voice must be
        provided"), so the endpoint configuration owns the default (its
        ``options["voice"]``) and the caller resolves it — the provider never
        guesses a voice.

        Args:
            text: The text to speak.
            config: Endpoint configuration (carries api_key, base_url, model).
            voice: Voice identifier (provider slug or saved-voice UUID).
            response_format: Audio container ("mp3", "wav", "flac", "opus").

        Returns:
            The audio bytes in the requested format.

        Raises:
            NotImplementedError: If the provider does not support synthesis.
        """
        raise NotImplementedError(f"{self.name} provider does not support speech synthesis")

    def synthesize_sync(
        self,
        text: str,
        config: AIEndpointConfig,
        voice: str,
        response_format: str = "mp3",
    ) -> bytes:
        """Synchronous version of :meth:`synthesize` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support speech synthesis")

    async def synthesize_stream(
        self,
        text: str,
        config: AIEndpointConfig,
        voice: str,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream speech synthesis as raw PCM audio chunks.

        The streaming counterpart of :meth:`synthesize`: instead of one
        buffered container, the provider yields audio as it is produced —
        the caller plays the chunks while the rest is still generating.
        The chunks are raw float32 LE PCM samples; the sample rate is the
        provider's (Mistral: 24 kHz), not negotiated here.

        Like the other optional capabilities, a provider that does not
        stream synthesis raises NotImplementedError — surfaced on the first
        chunk, so a fallback chain learns it at iteration time.

        Args:
            text: The text to speak.
            config: Endpoint configuration (carries api_key, base_url, model).
            voice: Voice identifier (provider slug or saved-voice UUID).

        Yields:
            Raw PCM audio bytes, in generation order.

        Raises:
            NotImplementedError: If the provider does not support streaming
                synthesis — on the first iteration.
        """
        raise NotImplementedError(f"{self.name} provider does not support streaming speech synthesis")
        yield b""  # pragma: no cover — makes this an async generator

    # ========== Batch (structured JSON) ==========

    async def submit_json_batch(
        self,
        requests: Sequence[AIBatchRequest],
        config: AIEndpointConfig,
        schema: Type[T],
        metadata: Optional[Dict[str, str]] = None,
        timeout_hours: Optional[int] = None,
    ) -> AIBatchJob:
        """
        Submit structured JSON requests to be processed asynchronously, as one job.

        Optional capability, like OCR: a provider that does not run batch jobs
        raises NotImplementedError. Each request is the one :meth:`chat_json`
        would send for its messages — same model, options and response schema —,
        answered later, usually at a lower price. The job runs on ``config``
        alone: a batch has one model, there is no fallback chain.

        Args:
            requests: The requests, each with a ``custom_id`` unique in the job.
            config: Endpoint configuration (model, api_key, options).
            schema: Pydantic model class every answer must validate against.
            metadata: Optional labels the provider keeps with the job.
            timeout_hours: Hours after which the job expires unfinished; the
                provider's default when None.

        Returns:
            The job as created.

        Raises:
            NotImplementedError: If the provider does not run batch jobs.
            ValueError: No request, a ``custom_id`` repeated, or more requests
                (or a larger input) than the provider takes in one job.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    def submit_json_batch_sync(
        self,
        requests: Sequence[AIBatchRequest],
        config: AIEndpointConfig,
        schema: Type[T],
        metadata: Optional[Dict[str, str]] = None,
        timeout_hours: Optional[int] = None,
    ) -> AIBatchJob:
        """Synchronous version of :meth:`submit_json_batch` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    async def get_batch(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """
        Where a batch job stands. The provider is polled: none calls back.

        Raises:
            NotImplementedError: If the provider does not run batch jobs.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    def get_batch_sync(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """Synchronous version of :meth:`get_batch` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    async def get_json_batch_results(
        self,
        job_id: str,
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> List[AIBatchResult[T]]:
        """
        The results of a batch job in a final state, each validated against
        ``schema`` like a :meth:`chat_json` answer. A request whose answer failed
        or does not validate carries its error; a request absent from the list was
        not processed.

        Raises:
            NotImplementedError: If the provider does not run batch jobs.
            ValueError: The job is not in a final state yet.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    def get_json_batch_results_sync(
        self,
        job_id: str,
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> List[AIBatchResult[T]]:
        """Synchronous version of :meth:`get_json_batch_results` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    async def cancel_batch(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """
        Ask the provider to stop a batch job; the requests already processed keep
        their results.

        Raises:
            NotImplementedError: If the provider does not run batch jobs.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    def cancel_batch_sync(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """Synchronous version of :meth:`cancel_batch` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    async def delete_batch_files(self, job_id: str, config: AIEndpointConfig) -> int:
        """
        Delete the files a batch job in a final state leaves with the provider (its
        requests and its answers), once its results are recorded. Best-effort: a
        file not deleted is logged. Returns the number of the job's files gone,
        deleted now or before, so a retried call is safe.

        Raises:
            NotImplementedError: If the provider does not run batch jobs.
            ValueError: The job is not in a final state yet.
        """
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    def delete_batch_files_sync(self, job_id: str, config: AIEndpointConfig) -> int:
        """Synchronous version of :meth:`delete_batch_files` for Celery workers."""
        raise NotImplementedError(f"{self.name} provider does not support batch jobs")

    # ========== Helpers ==========

    def get_base_url(self, config: AIEndpointConfig) -> str:
        """Get base URL from config or default."""
        return config.base_url or self.default_base_url

    @classmethod
    def get_available_models(cls) -> List[str]:
        """Return list of known models for this provider."""
        return []

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