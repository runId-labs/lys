"""
Mistral AI provider implementation.

This module implements the AIProvider interface for Mistral AI,
supporting both standard chat and structured JSON responses.
"""

import base64
import hashlib
import json
import logging
import re
from typing import AsyncGenerator, List, Dict, Any, Optional, Sequence, Type

import httpx

from lys.apps.ai.utils.providers.abstracts import (
    AIBatchJob,
    AIBatchRequest,
    AIBatchResult,
    AIBatchState,
    AIProvider,
    AIResponse,
    AIStreamChunk,
    TRUNCATION_FINISH_REASONS,
    T,
)
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIError,
    AIAuthError,
    AIRateLimitError,
    AIModelNotFoundError,
    AIProviderError,
    AITimeoutError,
    AIResponseTruncatedError,
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
        "voxtral-mini-latest",
    ]

    # Valid options that can be passed to Mistral API
    VALID_OPTIONS = {
        "temperature", "top_p", "max_tokens", "min_tokens",
        "stream", "stop", "random_seed", "safe_prompt",
        "response_format", "presence_penalty", "frequency_penalty",
        "reasoning_effort",
    }

    # Form fields the transcriptions endpoint accepts besides the file and the
    # model. Filtered like VALID_OPTIONS so a chat-only option in an endpoint
    # config cannot leak into a multipart transcription request.
    VALID_TRANSCRIPTION_OPTIONS = {
        "language", "diarize", "context_bias", "timestamp_granularities",
    }

    # Batch jobs: the requests are uploaded as a JSONL file, then the job created on it
    # (inline requests were refused at ~10 MB, 500 requests of ~20 KB, measured
    # 2026-11-21). The API's limits per job (docs "Known limitations"): this many
    # requests, and an input file of this size — the decimal reading of its 512 MB, the
    # lower one. Both are checked before any upload; a caller splits a larger set.
    MAX_BATCH_REQUESTS = 100_000
    MAX_BATCH_FILE_BYTES = 512 * 1000 * 1000

    # Batch job statuses, in provider-neutral terms. CANCELLATION_REQUESTED is still
    # moving: the job may finish requests before it stops.
    BATCH_STATES = {
        "QUEUED": AIBatchState.PENDING,
        "RUNNING": AIBatchState.PENDING,
        "CANCELLATION_REQUESTED": AIBatchState.PENDING,
        "SUCCESS": AIBatchState.COMPLETED,
        "FAILED": AIBatchState.FAILED,
        "TIMEOUT_EXCEEDED": AIBatchState.EXPIRED,
        "CANCELLED": AIBatchState.CANCELLED,
    }

    # A batch job or file id goes into a URL path: anything but these characters could
    # point the request at another endpoint.
    _BATCH_ID = re.compile(r"^[A-Za-z0-9_-]+$")

    @staticmethod
    def _cache_key_field(messages: List[Dict[str, Any]],
                         config: Optional[AIEndpointConfig] = None) -> Dict[str, str]:
        """Stable ``prompt_cache_key`` derived from the CACHEABLE system segments only.

        Mistral caches on the shared request prefix; the key groups requests that share
        that prefix (cached input tokens are billed at ~10%). It must therefore ignore the
        volatile segments — the consumer's volatile context layer, conversation summary,
        per-turn tool context — otherwise every turn lands in its own cache bucket and
        nothing is ever reused.

        Call this BEFORE :meth:`_flatten_system`: once flattened, the stable and volatile
        segments are one string and cannot be told apart.

        Measured on the API: two identical prompts under the same key reuse 100% of the
        prefix, under different keys 0%. The key must therefore stay identical across the
        turns of a conversation — hashing anything volatile sends every turn to its own
        cache bucket, which is what produced an alternating 0%/90% hit rate.
        """
        if config is not None and config.cache_key:
            # A caller that knows which exchange this is wins over anything inferred from the
            # text: it stays constant across the turns of that exchange, which is exactly what
            # the key has to do.
            return {"prompt_cache_key": f"conv-{config.cache_key}"}

        stable_parts: List[str] = []
        for message in messages:
            if message.get("role") != "system":
                continue
            content = message.get("content")
            if isinstance(content, list):
                # Segmented content: keep the segments flagged as cacheable.
                stable_parts.extend(
                    seg.get("text", "") for seg in content
                    if isinstance(seg, dict) and seg.get("cache")
                )
            elif isinstance(content, str) and content:
                # One message per segment, the flag sits on the message itself. The default
                # matches the sanitizer's (False): an unflagged segment is volatile, and
                # hashing it would defeat the whole point. The single unflagged system
                # message — the historical unsegmented shape — is handled below.
                if message.get("cache", False):
                    stable_parts.append(content)

        if not stable_parts:
            # Nothing declared cacheable. A lone plain system prompt is the unsegmented shape
            # and is stable by nature, so it still yields a key. Several unflagged segments
            # reach here only if the caller declared none cacheable: no key at all beats one
            # derived from volatile content.
            plain = [m.get("content") for m in messages if m.get("role") == "system"]
            if len(plain) == 1 and isinstance(plain[0], str) and plain[0]:
                stable_parts = [plain[0]]

        system = "\n\n".join(part for part in stable_parts if part)
        if not system:
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
        cache_field = self._cache_key_field(messages, config)
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            **cache_field,
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

        headers = self._headers(config)

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
        cache_field = self._cache_key_field(messages, config)
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            **cache_field,
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

        headers = self._headers(config)

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
        cache_field = self._cache_key_field(messages, config)
        messages = self._flatten_system(messages)
        base_url = self.get_base_url(config)

        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}

        payload = {
            "model": config.model,
            "messages": messages,
            "stream": True,
            **cache_field,
            **filtered_options,
        }

        if tools:
            cleaned_tools = [
                {k: v for k, v in tool.items() if not k.startswith("_")}
                for tool in tools
            ]
            payload["tools"] = cleaned_tools
            payload["tool_choice"] = "auto"

        headers = self._headers(config)

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

                        raw_content = delta.get("content")
                        content = self._extract_text(raw_content)
                        reasoning = self._extract_reasoning(raw_content)
                        tool_calls = delta.get("tool_calls")

                        yield AIStreamChunk(
                            content=content,
                            reasoning=reasoning,
                            tool_calls=tool_calls,
                            finish_reason=finish_reason,
                            usage=self._normalize_usage(data.get("usage")),
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
        payload = self._json_payload(messages, config, schema)
        base_url = self.get_base_url(config)

        headers = self._headers(config)

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
                raise self._validation_error(ai_response, schema, e)

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
        payload = self._json_payload(messages, config, schema)
        base_url = self.get_base_url(config)

        headers = self._headers(config)

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
                raise self._validation_error(ai_response, schema, e)

        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    def _json_payload(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> Dict[str, Any]:
        """The chat completions request of a structured JSON call: what a batch sends per request too."""
        cache_field = self._cache_key_field(messages, config)
        # Filter options to only include valid Mistral API parameters
        filtered_options = {k: v for k, v in config.options.items() if k in self.VALID_OPTIONS}
        return {
            "model": config.model,
            "messages": self._flatten_system(messages),
            "response_format": self._build_json_schema_response_format(schema),
            **cache_field,
            **filtered_options,
        }

    # ========== Batch (structured JSON) ==========

    def _batch_file(
        self,
        requests: Sequence[AIBatchRequest],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> bytes:
        """
        The job's input file, one JSON line per request: the body :meth:`chat_json`
        sends, the model set once on the job (a batch runs on one model).
        """
        if not requests:
            raise ValueError("A batch job needs at least one request")
        if len(requests) > self.MAX_BATCH_REQUESTS:
            raise ValueError(
                f"A batch job takes {self.MAX_BATCH_REQUESTS} requests at most, got {len(requests)}"
            )
        custom_ids = [request.custom_id for request in requests]
        if len(set(custom_ids)) != len(custom_ids):
            raise ValueError("Every request of a batch job needs its own custom_id")

        lines = []
        size = 0
        for request in requests:
            body = self._json_payload(request.messages, config, schema)
            body.pop("model")
            line = (json.dumps({"custom_id": request.custom_id, "body": body}, ensure_ascii=False) + "\n").encode()
            size += len(line)
            if size > self.MAX_BATCH_FILE_BYTES:
                # Stops as soon as the bound is passed: the rest is never encoded.
                raise ValueError(
                    f"A batch job's input file takes {self.MAX_BATCH_FILE_BYTES} bytes at most, passed at "
                    f"request {len(lines) + 1} of {len(requests)}: split the requests into smaller jobs"
                )
            lines.append(line)
        return b"".join(lines)

    @staticmethod
    def _batch_job_payload(
        file_id: str,
        config: AIEndpointConfig,
        metadata: Optional[Dict[str, str]],
        timeout_hours: Optional[int],
    ) -> Dict[str, Any]:
        """The job creation request, on the input file uploaded."""
        payload: Dict[str, Any] = {
            "model": config.model,
            "endpoint": "/v1/chat/completions",
            "input_files": [file_id],
        }
        if metadata:
            payload["metadata"] = metadata
        if timeout_hours is not None:
            payload["timeout_hours"] = timeout_hours
        return payload

    def _uploaded_file_id(self, response: httpx.Response) -> str:
        """The id of a file uploaded, its HTTP status checked first."""
        self._handle_error_status(response)
        file_id = response.json().get("id")
        if not isinstance(file_id, str) or not self._BATCH_ID.match(file_id):
            raise AIProviderError(f"Mistral file upload response without a valid id: {file_id!r}")
        return file_id

    async def _discard_input_file(self, client: httpx.AsyncClient, config: AIEndpointConfig, file_id: str) -> None:
        """
        Best-effort removal of an input file no job was created on: it holds the prompts.
        A failure is logged, never raised — the job's refusal is the error the caller gets.
        """
        try:
            response = await client.delete(self._batch_url(config, "files", file_id),
                                           headers=self._headers(config), timeout=config.timeout)
        except httpx.HTTPError as e:
            logger.warning("Mistral batch input file %s not deleted: %s", file_id, type(e).__name__)
            return
        if response.status_code != 200:
            logger.warning("Mistral batch input file %s not deleted: HTTP %s", file_id, response.status_code)

    def _discard_input_file_sync(self, client: httpx.Client, config: AIEndpointConfig, file_id: str) -> None:
        """Synchronous version of :meth:`_discard_input_file`."""
        try:
            response = client.delete(self._batch_url(config, "files", file_id),
                                     headers=self._headers(config), timeout=config.timeout)
        except httpx.HTTPError as e:
            logger.warning("Mistral batch input file %s not deleted: %s", file_id, type(e).__name__)
            return
        if response.status_code != 200:
            logger.warning("Mistral batch input file %s not deleted: HTTP %s", file_id, response.status_code)

    @staticmethod
    def _upload_request(config: AIEndpointConfig, content: bytes) -> Dict[str, Any]:
        """The multipart upload of a batch input file (no Content-Type: httpx sets the boundary)."""
        return {
            "headers": {"Authorization": f"Bearer {config.api_key}"},
            "data": {"purpose": "batch"},
            "files": {"file": ("batch.jsonl", content, "application/jsonl")},
            "timeout": config.timeout,
        }

    def _batch_url(self, config: AIEndpointConfig, kind: str, object_id: Optional[str] = None) -> str:
        """The URL of the batch jobs, of one job or of one file, its id checked first."""
        if object_id is None:
            return f"{self.get_base_url(config)}/{kind}"
        if not self._BATCH_ID.match(object_id):
            raise ValueError(f"Invalid Mistral {kind} id: {object_id!r}")
        return f"{self.get_base_url(config)}/{kind}/{object_id}"

    def _parse_batch_job(self, response: httpx.Response) -> AIBatchJob:
        """Read a batch job response, its HTTP status checked first."""
        self._handle_error_status(response)
        return self._batch_job(response.json())

    def _batch_job(self, data: Dict[str, Any]) -> AIBatchJob:
        """Read a batch job; a status this provider does not know is an error, never a guess."""
        if not data.get("id"):
            raise AIProviderError("Mistral batch job response without an id")
        state = self.BATCH_STATES.get(data.get("status"))
        if state is None:
            raise AIProviderError(f"Unknown Mistral batch job status: {data.get('status')!r}")
        try:
            # The API documents integers but its examples write them as strings.
            counts = {key: int(data.get(key) or 0)
                      for key in ("total_requests", "succeeded_requests", "failed_requests")}
        except (TypeError, ValueError) as e:
            raise AIProviderError(f"Mistral batch job {data['id']} reports a count that is not a number: {e}")
        return AIBatchJob(id=data["id"], state=state, provider=self.name, model=data.get("model") or "", **counts)

    def _finished_batch_job(self, response: httpx.Response) -> Dict[str, Any]:
        """
        The job of a results request, refused while it is still running: its results
        would be empty, read as requests never processed and sent again.
        """
        self._handle_error_status(response)
        data = response.json()
        job = self._batch_job(data)
        if not job.state.is_final:
            raise ValueError(f"Mistral batch job {job.id} is not finished: poll get_batch until state.is_final")
        return data

    def _batch_records(self, job: Dict[str, Any], files: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        The result records of a job: the lines of its output and error files
        (``files``: file id → content) — complete whatever the job's size —, else
        the ones the API returns inline (``outputs``).
        """
        if not files:
            outputs = job.get("outputs")
            return [record for record in outputs if isinstance(record, dict)] if isinstance(outputs, list) else []
        records = []
        for file_id, content in files.items():
            for line in content.splitlines():
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise AIProviderError(f"Mistral batch file {file_id} holds a line that is not JSON: {e}")
        return records

    def _parse_batch_record(self, record: Dict[str, Any], schema: Type[T]) -> Optional[AIBatchResult[T]]:
        """
        One result record, validated like a :meth:`chat_json` answer. Shape measured
        on the API (2026-11-21): ``{"custom_id", "response": {"status_code", "body"}}``,
        the body a chat completion. None for a record naming no request.
        """
        custom_id = record.get("custom_id")
        if not custom_id:
            logger.warning("Mistral batch result without custom_id, ignored")
            return None
        response = record.get("response") or {}
        status_code = response.get("status_code")
        body = response.get("body")
        if status_code != 200 or not isinstance(body, dict):
            detail = record.get("error") or body
            error = self._status_error(status_code) or AIProviderError(f"Mistral error: {status_code}")
            return AIBatchResult(
                custom_id=custom_id,
                error=type(error)(f"{error} (batch request {custom_id}): {str(detail)[:500]}"),
            )

        ai_response = self._parse_completion(body)
        self._warn_if_non_stop_finish(ai_response, schema)
        try:
            data = schema.model_validate_json(ai_response.content)
        except Exception as e:
            self._log_validation_failure(ai_response, schema, e)
            return AIBatchResult(custom_id=custom_id, error=self._validation_error(ai_response, schema, e),
                                 usage=ai_response.usage)
        return AIBatchResult(custom_id=custom_id, data=data, usage=ai_response.usage)

    def _parse_batch_results(
        self, job: Dict[str, Any], files: Dict[str, str], schema: Type[T],
    ) -> List[AIBatchResult[T]]:
        results = (self._parse_batch_record(record, schema) for record in self._batch_records(job, files))
        return [result for result in results if result is not None]

    @staticmethod
    def _result_file_ids(job: Dict[str, Any]) -> List[str]:
        """The output and error files holding the job's results."""
        return [file_id for file_id in (job.get("output_file"), job.get("error_file")) if file_id]

    @staticmethod
    def _headers(config: AIEndpointConfig) -> Dict[str, str]:
        """The headers of a JSON request to the Mistral API."""
        return {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}

    async def submit_json_batch(
        self,
        requests: Sequence[AIBatchRequest],
        config: AIEndpointConfig,
        schema: Type[T],
        metadata: Optional[Dict[str, str]] = None,
        timeout_hours: Optional[int] = None,
    ) -> AIBatchJob:
        """
        Create a batch job on Mistral's batch API: the requests uploaded as a JSONL file, the job on it.

        A job the API refuses leaves no input file behind: it is deleted. After a timeout
        it is kept — the job may have been created on it.
        """
        content = self._batch_file(requests, config, schema)
        try:
            async with httpx.AsyncClient() as client:
                upload = await client.post(self._batch_url(config, "files"), **self._upload_request(config, content))
                file_id = self._uploaded_file_id(upload)
                payload = self._batch_job_payload(file_id, config, metadata, timeout_hours)
                response = await client.post(self._batch_url(config, "batch/jobs"), headers=self._headers(config),
                                             json=payload, timeout=config.timeout)
                if response.status_code != 200:
                    await self._discard_input_file(client, config, file_id)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_job(response)

    def submit_json_batch_sync(
        self,
        requests: Sequence[AIBatchRequest],
        config: AIEndpointConfig,
        schema: Type[T],
        metadata: Optional[Dict[str, str]] = None,
        timeout_hours: Optional[int] = None,
    ) -> AIBatchJob:
        """Synchronous version of :meth:`submit_json_batch` for Celery workers."""
        content = self._batch_file(requests, config, schema)
        try:
            with httpx.Client() as client:
                upload = client.post(self._batch_url(config, "files"), **self._upload_request(config, content))
                file_id = self._uploaded_file_id(upload)
                payload = self._batch_job_payload(file_id, config, metadata, timeout_hours)
                response = client.post(self._batch_url(config, "batch/jobs"), headers=self._headers(config),
                                       json=payload, timeout=config.timeout)
                if response.status_code != 200:
                    self._discard_input_file_sync(client, config, file_id)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_job(response)

    async def get_batch(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """Read a batch job's status and counts."""
        url = self._batch_url(config, "batch/jobs", job_id)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._headers(config), timeout=config.timeout)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_job(response)

    def get_batch_sync(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """Synchronous version of :meth:`get_batch` for Celery workers."""
        url = self._batch_url(config, "batch/jobs", job_id)
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self._headers(config), timeout=config.timeout)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_job(response)

    async def get_json_batch_results(
        self,
        job_id: str,
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> List[AIBatchResult[T]]:
        """
        Read and validate a batch job's results: from its output and error files, else inline.

        Raises:
            ValueError: The job is not in a final state yet.
        """
        url = self._batch_url(config, "batch/jobs", job_id)
        headers = self._headers(config)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=config.timeout)
                job = self._finished_batch_job(response)
                if not self._result_file_ids(job):
                    # No result file: the job's results, if any, are only returned inline.
                    response = await client.get(url, headers=headers, params={"inline": "true"},
                                                timeout=config.timeout)
                    job = self._finished_batch_job(response)
                files = {}
                for file_id in self._result_file_ids(job):
                    file_response = await client.get(f"{self._batch_url(config, 'files', file_id)}/content",
                                                     headers=headers, timeout=config.timeout)
                    self._handle_error_status(file_response)
                    files[file_id] = file_response.text
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_results(job, files, schema)

    def get_json_batch_results_sync(
        self,
        job_id: str,
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> List[AIBatchResult[T]]:
        """Synchronous version of :meth:`get_json_batch_results` for Celery workers."""
        url = self._batch_url(config, "batch/jobs", job_id)
        headers = self._headers(config)
        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=config.timeout)
                job = self._finished_batch_job(response)
                if not self._result_file_ids(job):
                    # No result file: the job's results, if any, are only returned inline.
                    response = client.get(url, headers=headers, params={"inline": "true"}, timeout=config.timeout)
                    job = self._finished_batch_job(response)
                files = {}
                for file_id in self._result_file_ids(job):
                    file_response = client.get(f"{self._batch_url(config, 'files', file_id)}/content",
                                               headers=headers, timeout=config.timeout)
                    self._handle_error_status(file_response)
                    files[file_id] = file_response.text
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_results(job, files, schema)

    async def cancel_batch(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """Ask Mistral to stop a batch job."""
        url = f"{self._batch_url(config, 'batch/jobs', job_id)}/cancel"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._headers(config), timeout=config.timeout)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_job(response)

    def cancel_batch_sync(self, job_id: str, config: AIEndpointConfig) -> AIBatchJob:
        """Synchronous version of :meth:`cancel_batch` for Celery workers."""
        url = f"{self._batch_url(config, 'batch/jobs', job_id)}/cancel"
        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._headers(config), timeout=config.timeout)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_batch_job(response)

    # ========== Embeddings ==========

    def _embeddings_payload(self, texts: List[str], config: AIEndpointConfig) -> Dict[str, Any]:
        return {"model": config.model, "input": texts}

    def _parse_embeddings(self, response: httpx.Response, expected: int) -> List[List[float]]:
        """
        Read the vectors out of an embeddings response, in the order asked for.

        Sorted by index rather than trusted as returned: the API documents an index per
        item, and a silent reordering would attach every vector to the wrong message -
        a corruption nothing downstream could detect.
        """
        self._handle_error_status(response)

        data = response.json().get("data", [])
        if len(data) != expected:
            raise AIProviderError(
                f"Embeddings response holds {len(data)} vector(s) for {expected} input(s)"
            )

        return [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]

    async def embed(
        self,
        texts: List[str],
        config: AIEndpointConfig,
    ) -> List[List[float]]:
        """Embed texts through Mistral's embeddings endpoint."""
        if not texts:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.get_base_url(config)}/embeddings",
                    headers=self._headers(config),
                    json=self._embeddings_payload(texts, config),
                    timeout=config.timeout,
                )
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

        return self._parse_embeddings(response, len(texts))

    def embed_sync(
        self,
        texts: List[str],
        config: AIEndpointConfig,
    ) -> List[List[float]]:
        """Synchronous version of :meth:`embed` for Celery workers."""
        if not texts:
            return []

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.get_base_url(config)}/embeddings",
                    headers=self._headers(config),
                    json=self._embeddings_payload(texts, config),
                    timeout=config.timeout,
                )
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

        return self._parse_embeddings(response, len(texts))

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
        headers = self._headers(config)
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
        headers = self._headers(config)
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

    # ========== Transcription ==========

    def _transcription_data(
        self,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the multipart form fields for the transcriptions endpoint.

        The audio and its filename travel as the file part, not here. An explicit
        ``language`` argument wins over an option of the same name: the caller
        passing the language is the stronger, per-request signal.
        """
        data: Dict[str, Any] = {"model": config.model}
        data.update(
            {k: v for k, v in config.options.items() if k in self.VALID_TRANSCRIPTION_OPTIONS}
        )
        if language:
            data["language"] = language
        return data

    def _parse_transcription_response(self, response: httpx.Response) -> str:
        """Validate the transcription response and return its text.

        The endpoint is OpenAI-shaped: ``{"text": "..."}``. A 200 without a
        ``text`` key degrades to "" — an audio of silence transcribes to the
        same thing, and guessing between the two would invent an error.
        """
        self._handle_error_status(response)
        return response.json().get("text", "")

    async def transcribe(
        self,
        content: bytes,
        filename: str,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> str:
        """Async transcription via Mistral's ``/audio/transcriptions`` endpoint.

        The audio is sent as a multipart file part (httpx derives the boundary
        and the part content type from the filename), the response is
        OpenAI-shaped: ``{"text": "..."}``.
        """
        # No Content-Type header: httpx sets the multipart boundary itself.
        headers = {"Authorization": f"Bearer {config.api_key}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.get_base_url(config)}/audio/transcriptions",
                    headers=headers,
                    data=self._transcription_data(config, language),
                    files={"file": (filename, content)},
                    timeout=config.timeout,
                )
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_transcription_response(response)

    def transcribe_sync(
        self,
        content: bytes,
        filename: str,
        config: AIEndpointConfig,
        language: Optional[str] = None,
    ) -> str:
        """Synchronous version of :meth:`transcribe` for Celery workers."""
        headers = {"Authorization": f"Bearer {config.api_key}"}
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.get_base_url(config)}/audio/transcriptions",
                    headers=headers,
                    data=self._transcription_data(config, language),
                    files={"file": (filename, content)},
                    timeout=config.timeout,
                )
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_transcription_response(response)

    # ========== Synthesis (text-to-speech) ==========

    def _parse_synthesis_response(self, response: httpx.Response) -> bytes:
        """
        Validate the speech response and return its audio bytes.

        The endpoint returns ``{"audio_data": "<base64 audio>"}`` — the base64
        payload, not the JSON, is what the caller hands to its HTTP client. A
        200 without ``audio_data`` cannot be degraded to empty bytes the way
        silent audio degrades to "": an empty sound file is never a valid
        answer to a non-empty text, so it is an error.
        """
        self._handle_error_status(response)
        audio_data = response.json().get("audio_data")
        if not audio_data:
            raise AIValidationError("Synthesis response has no audio_data")
        return base64.b64decode(audio_data)

    async def synthesize(
        self,
        text: str,
        config: AIEndpointConfig,
        voice: str,
        response_format: str = "mp3",
    ) -> bytes:
        """Async speech synthesis via Mistral's ``/audio/speech`` endpoint.

        The voice is part of the request body, never optional: the API has no
        default voice ("Either ref_audio or voice must be provided"), so an
        empty ``voice`` reaching this method is a caller bug, surfaced by the
        API rather than silently worked around here.
        """
        headers = {"Authorization": f"Bearer {config.api_key}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.get_base_url(config)}/audio/speech",
                    headers=headers,
                    json={
                        "model": config.model,
                        "input": text,
                        "voice": voice,
                        "response_format": response_format,
                    },
                    timeout=config.timeout,
                )
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_synthesis_response(response)

    def synthesize_sync(
        self,
        text: str,
        config: AIEndpointConfig,
        voice: str,
        response_format: str = "mp3",
    ) -> bytes:
        """Synchronous version of :meth:`synthesize` for Celery workers."""
        headers = {"Authorization": f"Bearer {config.api_key}"}
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.get_base_url(config)}/audio/speech",
                    headers=headers,
                    json={
                        "model": config.model,
                        "input": text,
                        "voice": voice,
                        "response_format": response_format,
                    },
                    timeout=config.timeout,
                )
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")
        return self._parse_synthesis_response(response)

    async def synthesize_stream(
        self,
        text: str,
        config: AIEndpointConfig,
        voice: str,
    ) -> AsyncGenerator[bytes, None]:
        """Stream speech synthesis via Mistral's ``/audio/speech`` SSE endpoint.

        The audio arrives as Server-Sent Events — ``speech.audio.delta`` chunks
        carrying base64 float32 LE PCM at the provider's 24 kHz, closed by
        ``speech.stream.done``. The format is deliberately not configurable:
        raw PCM is the point of a stream (a container header would force the
        caller to buffer it back into one piece).
        """
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Accept": "text/event-stream",
        }
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.get_base_url(config)}/audio/speech",
                    headers=headers,
                    json={
                        "model": config.model,
                        "input": text,
                        "voice": voice,
                        "response_format": "pcm",
                        "stream": True,
                    },
                    timeout=config.timeout,
                ) as response:
                    self._handle_error_status(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = line[len("data:"):].strip()
                        if not payload:
                            continue
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            logger.warning(f"Mistral speech stream: invalid JSON: {payload}")
                            continue
                        if event.get("type") == "speech.audio.delta" and event.get("audio_data"):
                            yield base64.b64decode(event["audio_data"])
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    # ========== Helpers ==========

    @staticmethod
    def _validation_error(
        ai_response: AIResponse, schema: Type[T], error: Exception
    ) -> AIValidationError:
        """Build the validation error, flagging output-limit truncation as non-retryable."""
        message = f"Failed to validate response against schema {schema.__name__}: {error}"
        if ai_response.finish_reason in TRUNCATION_FINISH_REASONS:
            return AIResponseTruncatedError(message)
        return AIValidationError(message)

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

    @classmethod
    def _build_json_schema_response_format(cls, schema: Type[T]) -> Dict[str, Any]:
        """Build the ``response_format`` payload for Mistral's native ``json_schema`` mode.

        The Pydantic-generated schema is normalized for strict mode first (see
        :meth:`_strictify_schema`), then sent with ``strict`` enabled so the decoder enforces
        the schema constraint deterministically.

        Args:
            schema: Pydantic model class describing the expected response structure.

        Returns:
            A dict suitable for the Mistral chat completions ``response_format`` field.
        """
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": cls._strictify_schema(schema.model_json_schema()),
                "strict": True,
            },
        }

    @classmethod
    def _strictify_schema(cls, node: Any) -> Any:
        """Return a copy of a JSON schema that satisfies Mistral's strict-mode constraints.

        Strict mode drives a constrained decoder that rejects anything it cannot compile.
        A schema straight out of Pydantic breaks it: optional fields are absent from
        ``required`` and carry a ``default``. The decoder then fails mid-generation and the
        response comes back truncated with ``finish_reason="error"``, so the failure looks
        like a model problem rather than a payload problem.

        Three normalizations, applied recursively over every schema-object fragment:

        - every object lists ALL its properties in ``required`` (optionality is already
          carried by the ``anyOf: [T, null]`` shape Pydantic emits, which strict mode
          accepts),
        - every object sets ``additionalProperties: false``,
        - ``default`` keys are dropped (unsupported, and meaningless once required).

        ``properties`` and ``$defs`` are name -> schema maps, not schema objects themselves:
        their keys are field/model names chosen by the caller, not JSON Schema keywords, so
        they are recursed into without applying the ``default``-key filter to those names
        (a field legitimately named ``default`` must survive).

        Args:
            node: A JSON schema fragment (dict, list or scalar).

        Returns:
            A new fragment; the input is left untouched.
        """
        if isinstance(node, list):
            return [cls._strictify_schema(item) for item in node]
        if not isinstance(node, dict):
            return node

        result = {}
        for key, value in node.items():
            if key == "default":
                continue
            if key in ("properties", "$defs") and isinstance(value, dict):
                result[key] = {name: cls._strictify_schema(sub) for name, sub in value.items()}
            else:
                result[key] = cls._strictify_schema(value)

        properties = result.get("properties")
        if isinstance(properties, dict):
            result["required"] = list(properties.keys())
            result["additionalProperties"] = False

        return result

    @staticmethod
    def _status_error(status_code: Optional[int]) -> Optional[AIError]:
        """The error an HTTP status stands for; None for a success or a status left to the caller."""
        if status_code == 401:
            return AIAuthError("Invalid Mistral API key")
        if status_code == 429:
            return AIRateLimitError("Mistral rate limit exceeded")
        if status_code == 404:
            return AIModelNotFoundError("Mistral model not found")
        if status_code is not None and status_code >= 500:
            return AIProviderError(f"Mistral server error: {status_code}")
        return None

    def _handle_error_status(self, response: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        error = self._status_error(response.status_code)
        if error is not None:
            raise error
        if response.status_code != 200:
            logger.error(f"Mistral API error {response.status_code}: {response.text}")
            raise AIProviderError(f"Mistral error: {response.status_code}")

    @staticmethod
    def _extract_text(content: Any) -> Optional[str]:
        """Return the user-facing text of a message or streaming delta content.

        With ``reasoning_effort`` enabled the API returns a list of typed blocks
        instead of a plain string, mixing ``thinking`` blocks with ``text`` ones.
        Only the text blocks are user-facing. Returns ``None`` for a delta carrying no
        text (a pure thinking chunk), so streaming consumers can skip it.

        The reasoning is not dropped, only kept apart: see :meth:`_extract_reasoning`.
        """
        if not isinstance(content, list):
            return content

        texts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "".join(texts) if texts else None

    @staticmethod
    def _extract_reasoning(content: Any) -> Optional[str]:
        """Return the reasoning trace of a message or streaming delta content.

        Companion to :meth:`_extract_text`. Reasoning nests its text one level deeper
        (``{"type": "thinking", "thinking": [{"type": "text", "text": ...}]}``); a plain
        string is also accepted, the API has used both shapes. Returns ``None`` when there
        is no reasoning, so callers can pass the result through without branching.

        Never merge this into the answer: it is a draft, it names internal tools and the
        scoring vocabulary the system prompt forbids showing, and it is not written to be
        read. Exposing it is a caller decision — its value is that it starts streaming
        seconds after the request, long before the first answer token.
        """
        if not isinstance(content, list):
            return None

        chunks = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "thinking":
                continue
            nested = part.get("thinking")
            if isinstance(nested, list):
                chunks.extend(
                    item.get("text", "") for item in nested if isinstance(item, dict)
                )
            elif isinstance(nested, str):
                chunks.append(nested)
        text = "".join(chunks)
        return text or None

    @staticmethod
    def _normalize_usage(usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Expose Mistral's cached-prompt counter under the provider-neutral key.

        Mistral reports reused prefix tokens as ``usage.prompt_tokens_details.cached_tokens``
        (billed at ~10%). Without this mapping the caller stores nothing, and a session shows
        zero cache activity whether or not the cache actually worked — which is not the same
        thing.
        """
        if not usage:
            return usage
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        if cached is None:
            return usage
        return {**usage, "cache_read_tokens": cached}

    def _parse_response(self, response: httpx.Response) -> AIResponse:
        """Parse Mistral API response."""
        self._handle_error_status(response)
        return self._parse_completion(response.json())

    def _parse_completion(self, data: Dict[str, Any]) -> AIResponse:
        """Read a chat completion: of a direct call, or of one request of a batch job."""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # AIResponse.content is a plain string: a reasoning-only answer (no text block)
        # or an explicit null content must degrade to "" and never to None, otherwise
        # downstream length logging and schema validation break on a NoneType.
        content = self._extract_text(message.get("content", "")) or ""

        return AIResponse(
            content=content,
            tool_calls=message.get("tool_calls", []),
            usage=self._normalize_usage(data.get("usage")),
            model=data.get("model"),
            provider=self.name,
            finish_reason=choice.get("finish_reason"),
        )

    @classmethod
    def get_available_models(cls) -> List[str]:
        return cls.MODELS