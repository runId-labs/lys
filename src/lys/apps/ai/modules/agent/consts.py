"""
Agent constants.
"""

# Where a run stands. RUNNING while the loop works; one of the two others once it ended.
AGENT_RUN_RUNNING = "RUNNING"
AGENT_RUN_SUCCEEDED = "SUCCEEDED"
AGENT_RUN_FAILED = "FAILED"
AGENT_RUN_STATUSES = (AGENT_RUN_RUNNING, AGENT_RUN_SUCCEEDED, AGENT_RUN_FAILED)

# Model calls a run makes when its definition says nothing: the last one is made with tool
# calls refused, so a run always ends on an answer.
DEFAULT_AGENT_MAX_ITERATIONS = 15

# Model calls of the correction round a report check opens: enough to re-read the cells or
# texts it names, then rewrite the analysis.
DEFAULT_AGENT_REVISION_ITERATIONS = 6

# The only tool an agent may hold that is not a webservice: exact arithmetic, which reads no
# data and writes nothing.
AGENT_PURE_TOOLS = frozenset({"calculate"})

# The last call of the loop: tool calls refused, the analysis written whole. It is the call's
# own, never kept in the transcript.
AGENT_FINAL_ROUND_INSTRUCTION = (
    "No more tool calls are allowed: write your complete analysis now, from what the tools "
    "returned. Keep every figure with its source and every calculation with its result, and "
    "say what you could not read or check."
)

# The formatting call: the analysis turned into the report's schema, nothing added.
AGENT_REPORT_INSTRUCTION = (
    "Turn the analysis below into the requested report. Use only what the analysis states: "
    "add no figure, source or conclusion of your own, and leave a field empty when the "
    "analysis says nothing of it."
)

# The correction round's message: what the check found, the analysis rewritten from it.
AGENT_CORRECTION_INSTRUCTION = (
    "A check of your analysis against its sources found the points below wrong. Re-read what you "
    "need, then write your complete analysis again: correct each point from the source, or "
    "remove it when the source does not support it. Change nothing else."
)

# Said when the check itself could not run: the analysis stands, unchecked.
AGENT_ANALYSIS_UNCHECKED = "The analysis could not be checked against its sources."

# Upper bound, in seconds, of the trace's closing write: shielded from a cancellation, so a
# store that stops answering would hold the caller forever without it.
AGENT_TRACE_CLOSE_TIMEOUT = 10
