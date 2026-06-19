"""
Anthropic (Claude) provider implementation.

This module implements the AIProvider interface for Anthropic's Messages API,
supporting standard chat, streaming and structured JSON responses.

The rest of lys (conversation service, stored history) speaks the
OpenAI/Mistral-compatible message shape: a flat ``messages`` list with
``system``/``user``/``assistant``/``tool`` roles, assistant ``tool_calls`` and
``role: tool`` responses keyed by ``tool_call_id``. Anthropic's API uses a
different shape: a top-level ``system`` field plus ``tool_use`` / ``tool_result``
content blocks. This provider translates between the two in both directions so
no calling code has to change when an endpoint switches to ``provider="anthropic"``.
"""

import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple, Type

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

# Anthropic requires max_tokens on every request. Kept high enough not to truncate
# structured analysis payloads; override per-endpoint via options.max_tokens.
DEFAULT_MAX_TOKENS = 8192

# Anthropic allows at most 4 prompt-cache breakpoints (cache_control blocks) per request.
_MAX_CACHE_BREAKPOINTS = 4

# Anthropic API version pin (sent as the anthropic-version header).
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    """Anthropic (Claude) provider implementation."""

    name = "anthropic"
    default_base_url = "https://api.anthropic.com/v1"

    MODELS = [
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    ]

    # Options accepted by the Messages API. Mistral-specific keys (random_seed,
    # safe_prompt, response_format, ...) are filtered out. "stop" is remapped to
    # "stop_sequences" by _prepare.
    VALID_OPTIONS = {"temperature", "top_p", "top_k", "stop_sequences", "max_tokens"}

    # Sampling parameters were removed on Opus 4.7+ and return HTTP 400 if sent.
    # For the affected models they are dropped (with a warning) instead of
    # forwarded; steer those models via prompting instead.
    SAMPLING_OPTIONS = {"temperature", "top_p", "top_k"}
    MODELS_REJECTING_SAMPLING = ("claude-opus-4-8", "claude-opus-4-7")

    # ========== Standard Chat ==========

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse:
        """Send a chat request to the Anthropic Messages API."""
        payload, headers, base_url = self._prepare(messages, config, tools=tools)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/messages",
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
        payload, headers, base_url = self._prepare(messages, config, tools=tools)
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/messages",
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
        """Stream a chat response, translating Anthropic SSE events into AIStreamChunk.

        Anthropic streams typed events (``content_block_start``, ``content_block_delta``,
        ``message_delta``, ...) rather than OpenAI-style choice deltas. Tool calls arrive
        as a ``tool_use`` block opening followed by ``input_json_delta`` fragments. We
        re-emit them in the delta shape the conversation service accumulates: each chunk
        carries ``tool_calls=[{"index", "id", "function": {"name", "arguments"}}]`` where
        ``arguments`` is the partial JSON string, concatenated downstream by content-block
        index.
        """
        payload, headers, base_url = self._prepare(messages, config, tools=tools, stream=True)
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/messages",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                ) as response:
                    if response.status_code != 200:
                        await response.aread()
                    self._handle_error_status(response)

                    # Anthropic reports input_tokens only in message_start; carry it
                    # forward so the final usage chunk is complete (prompt + completion).
                    stream_state: Dict[str, Any] = {"input_tokens": None, "tool_arg_seen": {}}
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            logger.warning(f"Anthropic stream: invalid JSON: {data_str}")
                            continue

                        chunk = self._translate_stream_event(event, stream_state)
                        if chunk is not None:
                            yield chunk
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    def _translate_stream_event(
        self, event: Dict[str, Any], stream_state: Dict[str, Any]
    ) -> Optional[AIStreamChunk]:
        """Map a single Anthropic SSE event to an AIStreamChunk, or None to skip it.

        ``stream_state`` carries the prompt token count across events, since Anthropic
        only reports ``input_tokens`` in ``message_start`` while ``output_tokens`` lands
        in ``message_delta``.
        """
        event_type = event.get("type")

        if event_type == "message_start":
            message = event.get("message") or {}
            usage = message.get("usage") or {}
            if usage.get("input_tokens") is not None:
                stream_state["input_tokens"] = usage["input_tokens"]
            # Model and prompt-cache usage are only reported in message_start; carry forward.
            if message.get("model"):
                stream_state["model"] = message["model"]
            if usage.get("cache_creation_input_tokens") is not None:
                stream_state["cache_write_tokens"] = usage["cache_creation_input_tokens"]
            if usage.get("cache_read_input_tokens") is not None:
                stream_state["cache_read_tokens"] = usage["cache_read_input_tokens"]
            return None

        if event_type == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                # Open a tool call: emit id + name with empty arguments. The content-block
                # index becomes the accumulator key; input_json_delta fragments follow.
                # Track the index so content_block_stop can backfill "{}" if the tool has
                # no input (Anthropic streams no input_json_delta for empty-arg calls).
                stream_state.setdefault("tool_arg_seen", {})[event.get("index", 0)] = False
                return AIStreamChunk(
                    tool_calls=[{
                        "index": event.get("index", 0),
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {"name": block.get("name", ""), "arguments": ""},
                    }],
                    provider=self.name,
                )
            return None

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                return AIStreamChunk(content=delta.get("text", ""), provider=self.name)
            if delta_type == "input_json_delta":
                partial = delta.get("partial_json", "")
                if partial:
                    seen = stream_state.get("tool_arg_seen")
                    if seen is not None:
                        seen[event.get("index", 0)] = True
                return AIStreamChunk(
                    tool_calls=[{
                        "index": event.get("index", 0),
                        "function": {"arguments": partial},
                    }],
                    provider=self.name,
                )
            return None

        if event_type == "message_delta":
            delta = event.get("delta", {})
            finish_reason = self._map_finish_reason(delta.get("stop_reason"))
            usage = self._merge_stream_usage(stream_state, event.get("usage"))
            if finish_reason is None and usage is None:
                return None
            return AIStreamChunk(
                finish_reason=finish_reason,
                usage=usage,
                model=stream_state.get("model"),
                provider=self.name,
            )

        if event_type == "content_block_stop":
            # A tool_use block that received no input_json_delta has empty arguments;
            # backfill "{}" so the downstream json.loads of the accumulated arguments
            # succeeds (Mistral always emits "{}" for no-arg calls; Anthropic emits
            # nothing). Text blocks are untracked, so this only fires for empty tools.
            seen = stream_state.get("tool_arg_seen", {})
            idx = event.get("index", 0)
            if idx in seen and not seen[idx]:
                return AIStreamChunk(
                    tool_calls=[{"index": idx, "function": {"arguments": "{}"}}],
                    provider=self.name,
                )
            return None

        # message_stop, ping: nothing to forward.
        return None

    @staticmethod
    def _merge_stream_usage(
        stream_state: Dict[str, Any], delta_usage: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, int]]:
        """Combine the carried prompt tokens with the streamed completion tokens."""
        prompt = stream_state.get("input_tokens")
        completion = (delta_usage or {}).get("output_tokens")
        merged: Dict[str, int] = {}
        if prompt is not None:
            merged["prompt_tokens"] = prompt
        if completion is not None:
            merged["completion_tokens"] = completion
        if prompt is not None and completion is not None:
            merged["total_tokens"] = prompt + completion
        cache_read = stream_state.get("cache_read_tokens")
        cache_write = stream_state.get("cache_write_tokens")
        if cache_read is not None:
            merged["cache_read_tokens"] = cache_read
        if cache_write is not None:
            merged["cache_write_tokens"] = cache_write
        return merged or None

    # ========== JSON Methods ==========

    async def chat_json(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Chat constrained to a Pydantic schema via Anthropic forced tool use.

        Anthropic has no native ``response_format: json_schema`` mode. Instead the schema
        is exposed as a single tool and ``tool_choice`` forces the model to call it; the
        tool-call ``input`` is the structured object, validated against ``schema``.
        """
        tool = self._schema_to_tool(schema)
        payload, headers, base_url = self._prepare(
            messages, config, tools=[tool], tool_choice={"type": "tool", "name": tool["name"]}
        )
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/messages",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )
            ai_response = self._parse_response(response)
            return self._validate_tool_output(ai_response, schema)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    def chat_json_sync(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        schema: Type[T],
    ) -> T:
        """Synchronous version of :meth:`chat_json` for Celery workers."""
        tool = self._schema_to_tool(schema)
        payload, headers, base_url = self._prepare(
            messages, config, tools=[tool], tool_choice={"type": "tool", "name": tool["name"]}
        )
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{base_url}/messages",
                    headers=headers,
                    json=payload,
                    timeout=config.timeout,
                )
            ai_response = self._parse_response(response)
            return self._validate_tool_output(ai_response, schema)
        except httpx.TimeoutException:
            raise AITimeoutError(f"Request timed out after {config.timeout}s")

    # ========== Payload building ==========

    def _prepare(
        self,
        messages: List[Dict[str, Any]],
        config: AIEndpointConfig,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, str], str]:
        """Build the (payload, headers, base_url) triple for a Messages API call."""
        base_url = self.get_base_url(config)
        system, anthropic_messages = self._translate_messages(messages)

        options = dict(config.options or {})
        if "stop" in options and "stop_sequences" not in options:
            options["stop_sequences"] = options.pop("stop")
        filtered_options = {k: v for k, v in options.items() if k in self.VALID_OPTIONS}
        max_tokens = filtered_options.pop("max_tokens", None) or config.options.get(
            "max_tokens", DEFAULT_MAX_TOKENS
        )
        if self._rejects_sampling_params(config.model):
            dropped = [k for k in self.SAMPLING_OPTIONS if k in filtered_options]
            if dropped:
                logger.warning(
                    "Anthropic model %s rejects sampling parameters %s (HTTP 400); "
                    "dropping them. Steer this model via prompting instead.",
                    config.model, dropped,
                )
                filtered_options = {
                    k: v for k, v in filtered_options.items() if k not in self.SAMPLING_OPTIONS
                }

        payload: Dict[str, Any] = {
            "model": config.model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
            **filtered_options,
        }
        structured = isinstance(system, list)
        has_history = any(m.get("role") == "assistant" for m in anthropic_messages)
        if isinstance(system, str):
            # Single cacheable system block (one breakpoint) — historical shape. Cached
            # input tokens are billed at ~10% (5-min TTL).
            payload["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        elif structured:
            # One breakpoint per cacheable layer, so a change in a later layer (e.g. the page
            # prompt) does not bust the cache of an earlier, more stable one. Anthropic caps
            # cache_control at 4 per request; the tools block and the rolling last-message
            # breakpoint each reserve one, so the cacheable system segments share the remainder
            # — the FIRST (most stable) ones kept: a breakpoint on an earlier layer survives a
            # change in any later layer, whereas the rolling last-message breakpoint already
            # caches the longest prefix when everything is stable (a tail breakpoint here would
            # be redundant with it). Segments are ordered most-stable-first.
            cacheable = [i for i, seg in enumerate(system) if seg.get("cache")]
            reserved = (1 if tools else 0) + (1 if has_history else 0)
            budget = max(0, _MAX_CACHE_BREAKPOINTS - reserved)
            breakpoints = set(cacheable[:budget]) if budget else set()
            blocks: List[Dict[str, Any]] = []
            for i, seg in enumerate(system):
                block: Dict[str, Any] = {"type": "text", "text": seg["text"]}
                if i in breakpoints:
                    block["cache_control"] = {"type": "ephemeral"}
                blocks.append(block)
            payload["system"] = blocks
        if tools:
            translated_tools = self._translate_tools(tools)
            if structured and translated_tools:
                # Cache the tool block independently, so it survives a per-page system change.
                translated_tools[-1] = {
                    **translated_tools[-1], "cache_control": {"type": "ephemeral"}
                }
            payload["tools"] = translated_tools
            payload["tool_choice"] = tool_choice or {"type": "auto"}
        if has_history:
            # Rolling breakpoint on the last message: caches the whole prefix (tools +
            # system + history) up to the prior turn when it is byte-stable across turns.
            # Gated on the presence of a prior assistant turn — not on the system-prompt
            # shape — so any multi-turn consumer benefits, while a one-shot call (no prior
            # assistant message) never pays for a cache write it will not read back.
            last_content = anthropic_messages[-1].get("content")
            if isinstance(last_content, list) and last_content:
                last_content[-1] = {
                    **last_content[-1], "cache_control": {"type": "ephemeral"}
                }
        if stream:
            payload["stream"] = True

        headers = {
            "x-api-key": config.api_key or "",
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        return payload, headers, base_url

    @staticmethod
    def _translate_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Translate OpenAI/Mistral-shaped tool defs to Anthropic tool defs.

        Accepts either already-Anthropic tools ({"name", "input_schema"}) or
        OpenAI-style ({"type": "function", "function": {"name", "description", "parameters"}}).
        Internal ``_``-prefixed keys (e.g. ``_graphql``) are stripped.
        """
        translated = []
        for tool in tools:
            if "input_schema" in tool:
                # Already Anthropic-shaped (e.g. from _schema_to_tool).
                translated.append({k: v for k, v in tool.items() if not k.startswith("_")})
                continue
            fn = tool.get("function", tool)
            translated.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return translated

    @staticmethod
    def _translate_messages(
        messages: List[Dict[str, Any]],
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Translate lys (OpenAI/Mistral-shaped) messages to Anthropic (system, messages).

        - ``system`` role -> returned separately as the top-level system string.
        - ``user`` -> user message (string content preserved as-is).
        - ``assistant`` with ``tool_calls`` -> assistant message with optional text block
          plus one ``tool_use`` block per call (arguments JSON-parsed into ``input``).
        - ``tool`` -> ``tool_result`` block; consecutive tool messages are merged into a
          single user turn, as Anthropic expects all results for the prior assistant turn
          grouped together.
        Multiple ``system`` messages are concatenated (blank-line separated, input order)
        rather than dropped, matching ``sanitize_llm_messages``. Consecutive same-role
        turns are merged to satisfy Anthropic's strict alternation.
        """
        system_parts: List[Dict[str, Any]] = []  # ordered {"text", "cache"} segments
        out: List[Dict[str, Any]] = []

        def append(role: str, blocks: List[Dict[str, Any]]) -> None:
            # Anthropic requires strict user/assistant alternation. Merge any consecutive
            # same-role turns by concatenating their content blocks.
            if out and out[-1]["role"] == role:
                out[-1]["content"].extend(blocks)
            else:
                out.append({"role": role, "content": list(blocks)})

        def text_block(content: Any) -> List[Dict[str, Any]]:
            # Normalize free text to a single text block; skip empty (Anthropic rejects
            # empty text blocks) so an empty turn contributes nothing to the merge.
            text = content if isinstance(content, str) else (json.dumps(content) if content else "")
            return [{"type": "text", "text": text}] if text else []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                if isinstance(content, list):
                    # Structured system: ordered cacheable/volatile segments.
                    for seg in content:
                        if isinstance(seg, dict):
                            text, cache = seg.get("text") or "", bool(seg.get("cache"))
                        else:
                            text = seg if isinstance(seg, str) else json.dumps(seg)
                            cache = True
                        if text:
                            system_parts.append({"text": text, "cache": cache})
                elif isinstance(content, str):
                    if content:
                        system_parts.append({"text": content, "cache": True})
                elif content:
                    system_parts.append({"text": json.dumps(content), "cache": True})
            elif role == "tool":
                append("user", [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": content if isinstance(content, str) else json.dumps(content),
                }])
            elif role == "assistant" and msg.get("tool_calls"):
                blocks = text_block(content)
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": AnthropicProvider._safe_json(fn.get("arguments", "{}")),
                    })
                append("assistant", blocks)
            else:
                # Plain user/assistant text turn.
                append(role or "user", text_block(content))

        # Drop any turn left empty after normalization (e.g. an empty assistant ack).
        out = [turn for turn in out if turn["content"]]
        # A single cacheable block collapses to a plain string (one cache_control — the
        # historical shape); otherwise hand the ordered segments to _prepare.
        if not system_parts:
            system = None
        elif len(system_parts) == 1 and system_parts[0]["cache"]:
            system = system_parts[0]["text"]
        else:
            system = system_parts
        return system, out

    @staticmethod
    def _safe_json(raw: Any) -> Dict[str, Any]:
        """Parse a tool-arguments JSON string into a dict, tolerating bad input."""
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    # ========== Response parsing ==========

    def _parse_response(self, response: httpx.Response) -> AIResponse:
        """Parse an Anthropic Messages response into the standardized AIResponse.

        Text blocks are concatenated into ``content``; ``tool_use`` blocks are re-emitted
        as OpenAI/Mistral-shaped ``tool_calls`` (``function.arguments`` is the JSON-encoded
        ``input``) so the conversation service consumes them unchanged.
        """
        self._handle_error_status(response)
        data = response.json()

        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for block in data.get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {})),
                    },
                })

        return AIResponse(
            content="".join(text_parts),
            tool_calls=tool_calls,
            usage=self._normalize_usage(data.get("usage")),
            model=data.get("model"),
            provider=self.name,
            finish_reason=self._map_finish_reason(data.get("stop_reason")),
        )

    def _validate_tool_output(self, ai_response: AIResponse, schema: Type[T]) -> T:
        """Extract the forced tool-call input and validate it against ``schema``."""
        if not ai_response.tool_calls:
            logger.warning(
                "Anthropic returned no tool_use for %s (finish_reason=%s)",
                schema.__name__, ai_response.finish_reason,
            )
            raise AIValidationError(
                f"Expected a tool call for schema {schema.__name__}, got none"
            )
        arguments = ai_response.tool_calls[0]["function"]["arguments"]
        try:
            return schema.model_validate_json(arguments)
        except Exception as e:
            logger.warning(
                "Anthropic response validation failed for %s: %s (finish_reason=%s)",
                schema.__name__, e, ai_response.finish_reason,
            )
            raise AIValidationError(
                f"Failed to validate response against schema {schema.__name__}: {e}"
            )

    @staticmethod
    def _map_finish_reason(stop_reason: Optional[str]) -> Optional[str]:
        """Map Anthropic stop_reason to the OpenAI/Mistral-style finish_reason vocabulary."""
        if stop_reason is None:
            return None
        return {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls",
        }.get(stop_reason, stop_reason)

    @staticmethod
    def _normalize_usage(usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, int]]:
        """Map Anthropic usage (input_tokens/output_tokens) to prompt/completion/total."""
        if not usage:
            return None
        prompt = usage.get("input_tokens")
        completion = usage.get("output_tokens")
        normalized: Dict[str, int] = {}
        if prompt is not None:
            normalized["prompt_tokens"] = prompt
        if completion is not None:
            normalized["completion_tokens"] = completion
        if prompt is not None and completion is not None:
            normalized["total_tokens"] = prompt + completion
        cache_write = usage.get("cache_creation_input_tokens")
        cache_read = usage.get("cache_read_input_tokens")
        if cache_write is not None:
            normalized["cache_write_tokens"] = cache_write
        if cache_read is not None:
            normalized["cache_read_tokens"] = cache_read
        return normalized or None

    def _handle_error_status(self, response: httpx.Response) -> None:
        """Check response status and raise the appropriate AIError."""
        if response.status_code == 401:
            raise AIAuthError("Invalid Anthropic API key")
        if response.status_code == 429:
            raise AIRateLimitError("Anthropic rate limit exceeded")
        if response.status_code == 404:
            raise AIModelNotFoundError("Anthropic model not found")
        if response.status_code >= 500:
            raise AIProviderError(f"Anthropic server error: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"Anthropic API error {response.status_code}: {response.text}")
            raise AIProviderError(f"Anthropic error: {response.status_code}")

    @classmethod
    def _rejects_sampling_params(cls, model: str) -> bool:
        """Return True if ``model`` rejects temperature/top_p/top_k (Opus 4.7+)."""
        return model.startswith(cls.MODELS_REJECTING_SAMPLING)

    @classmethod
    def get_available_models(cls) -> List[str]:
        return cls.MODELS