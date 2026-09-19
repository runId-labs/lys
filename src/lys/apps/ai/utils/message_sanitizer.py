"""
LLM message-list sanitizer.

Enforces the message-ordering contract shared by major LLM providers
(Mistral, OpenAI, Anthropic), so the providers never reject a malformed
conversation history regardless of how it was reconstructed upstream.

Rules enforced:
- Leading `system` messages (a contiguous run starting at index 0) are merged
  into a single header at index 0 (e.g. an endpoint-level base prompt prepended
  on top of a conversation-level system prompt), their `content` concatenated
  with a blank line separator, preserving input order. No system content is
  dropped silently. If any source system message carries a truthy ``cache``
  flag, the segment boundaries are preserved instead (content becomes an ordered
  list of ``{"text", "cache"}`` blocks) so a provider can place a prompt-cache
  breakpoint between the stable prefix and the volatile tail.
- A `system` message placed after the first non-system message is a deliberate
  turn-scoped instruction (page prompt, focus marker, per-turn tool context) and
  is never hoisted to the header: doing so would move volatile text in front of
  the conversation history and bust the prompt cache on the whole exchange. It
  is kept in place, rebuilt as an explicitly non-cacheable segment so a provider
  that infers cacheability from plain-string content never marks it cacheable
  by accident.
- Each `tool` message is reattached immediately after the `assistant` message
  whose `tool_calls[].id` matches its `tool_call_id`.
- `tool` messages with no matching parent are dropped (orphans).
- For each `assistant.tool_calls[]` entry without a matching tool response,
  a synthetic placeholder tool message is injected, so every tool_call has a
  paired response (otherwise Mistral raises "Not the same number of function
  calls and responses").
- Non-system, non-tool messages keep their relative order.
"""

import json
from typing import Any, Dict, List


_INTERRUPTED_TOOL_RESULT = json.dumps({"error": "tool execution interrupted"})


def sanitize_llm_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return messages

    # Only the LEADING system messages form the header. A system message placed after the
    # history is a deliberate turn-scoped instruction: hoisting it would move volatile text
    # in front of the history and bust the prompt cache on the whole conversation, which is
    # exactly what placing it late avoids. It is passed through where the caller put it.
    first_non_system = next(
        (i for i, m in enumerate(messages) if m.get("role") != "system"), len(messages)
    )

    tool_responses_by_id: Dict[str, Dict[str, Any]] = {}
    system_segments: List[tuple] = []  # (content, cache)
    for index, msg in enumerate(messages):
        role = msg.get("role")
        if role == "tool":
            tcid = msg.get("tool_call_id")
            if tcid:
                tool_responses_by_id[tcid] = msg
        elif role == "system" and index < first_non_system:
            content = msg.get("content")
            if content:
                system_segments.append((content, bool(msg.get("cache", False))))

    result: List[Dict[str, Any]] = []
    if system_segments:
        # Segment boundaries survive as soon as there are several, cacheable or not: flattening
        # is lossy, and a consumer cannot then tell a stable prefix from a volatile tail. A
        # provider deriving a prompt-cache key from the system content would hash the volatile
        # part and send every turn to its own cache bucket. Providers wanting a plain string
        # flatten it back themselves.
        if any(cache for _, cache in system_segments) or len(system_segments) > 1:
            # At least one segment is marked cacheable: preserve the segment boundaries so
            # a provider supporting prompt caching can place a breakpoint between the stable
            # prefix and the volatile tail. Plain-string consumers flatten this back.
            result.append({
                "role": "system",
                "content": [{"text": c, "cache": cache} for c, cache in system_segments],
            })
        else:
            result.append({
                "role": "system",
                "content": "\n\n".join(c for c, _ in system_segments),
            })

    for index, msg in enumerate(messages):
        role = msg.get("role")

        if role == "tool":
            continue

        if role == "system":
            if index < first_non_system:
                continue
            # Late system message: keep it in place, but rebuild it as an explicitly
            # non-cacheable segment. A bare string would let a provider that infers
            # cacheability from plain-string content (Anthropic defaults such content to
            # cacheable) mark it cacheable by accident — the exact thing placing it after
            # the history is meant to avoid.
            content = msg.get("content")
            if content:
                result.append({"role": "system", "content": [{"text": content, "cache": False}]})
            continue

        result.append(msg)

        if role == "assistant" and msg.get("tool_calls"):
            for tool_call in msg["tool_calls"]:
                tcid = tool_call.get("id")
                if not tcid:
                    continue
                tool_msg = tool_responses_by_id.get(tcid)
                if tool_msg is not None:
                    result.append(tool_msg)
                else:
                    result.append({
                        "role": "tool",
                        "tool_call_id": tcid,
                        "content": _INTERRUPTED_TOOL_RESULT,
                    })

    return result