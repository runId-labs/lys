"""
LLM message-list sanitizer.

Enforces the message-ordering contract shared by major LLM providers
(Mistral, OpenAI, Anthropic), so the providers never reject a malformed
conversation history regardless of how it was reconstructed upstream.

Rules enforced:
- At most one `system` message, placed at index 0. When the input contains
  multiple system messages (e.g. an endpoint-level base prompt prepended on
  top of a conversation-level system prompt), their `content` is concatenated
  with a blank line separator, preserving input order. No system content is
  dropped silently.
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

    tool_responses_by_id: Dict[str, Dict[str, Any]] = {}
    system_contents: List[str] = []
    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            tcid = msg.get("tool_call_id")
            if tcid:
                tool_responses_by_id[tcid] = msg
        elif role == "system":
            content = msg.get("content")
            if content:
                system_contents.append(content)

    result: List[Dict[str, Any]] = []
    if system_contents:
        result.append({
            "role": "system",
            "content": "\n\n".join(system_contents),
        })

    for msg in messages:
        role = msg.get("role")

        if role == "system" or role == "tool":
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