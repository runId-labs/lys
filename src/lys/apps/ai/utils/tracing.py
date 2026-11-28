"""
What a trace keeps of a model call (``AIAgentRun.calls``), and its totals.

Shared by everything traced in ``ai_agent_run``: an agent's loop, and the specialists that run a
call or a loop of their own (``AIAgentService.record``), so what a turn cost reads the same way
whoever spent it.
"""

from typing import Any, Dict, List, Optional

# Provider usage keys -> trace columns.
_USAGE_COLUMNS = (
    ("tokens_in", "prompt_tokens"),
    ("tokens_out", "completion_tokens"),
    ("cache_read_tokens", "cache_read_tokens"),
    ("cache_write_tokens", "cache_write_tokens"),
)


def traced_call(
    kind: str, latency_ms: int, usage: Optional[Dict[str, Any]], model: Optional[str], tool_calls: int = 0,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One model call as a trace keeps it (``AIAgentRun.calls``): its kind, its latency, its tokens
    (a provider's ``usage``), the model that answered, the tools it asked for, and its error.
    """
    entry = {"kind": kind, "latency_ms": latency_ms, "tool_calls": tool_calls, "model": model}
    entry.update({column: (usage or {}).get(key) for column, key in _USAGE_COLUMNS})
    if error is not None:
        entry["error"] = error
    return entry


def call_totals(calls: List[Dict[str, Any]], tool_calls: int) -> Dict[str, Optional[int]]:
    """A trace's columns, added up over its calls; a total no provider reported stays unknown."""
    totals: Dict[str, Optional[int]] = {
        "model_calls": len(calls),
        "tool_calls": tool_calls,
        "latency_ms": sum(call["latency_ms"] for call in calls),
    }
    for column, _ in _USAGE_COLUMNS:
        values = [call[column] for call in calls if call.get(column) is not None]
        totals[column] = sum(values) if values else None
    return totals
