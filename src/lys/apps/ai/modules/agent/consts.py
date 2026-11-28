"""
Agent constants.
"""
from datetime import timedelta

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

# How long a run may be followed up once it ended: the follow-up reads what the run read under the
# user's rights of the time, and data that has moved since; past it, the caller asks a new run.
DEFAULT_AGENT_CONTINUATION_TTL = timedelta(hours=24)

# What a follow-up reads in place of each tool result of the run it continues: the reasoning and the
# calls stay, the results are dropped (a run reads up to a million characters), and the agent calls
# again what it needs — the tool-result clearing of context editing.
AGENT_CLEARED_TOOL_RESULT = (
    "[Result cleared to keep the context short. Call the tool again if you need what it returned.]"
)

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

# What a report is written from (AgentDefinition.report_source). From the ANALYSIS: the report
# copies what the agent wrote — the tool history stays out of the structured call, so any provider
# takes it, at the cost of writing everything twice. From the READINGS: the report is written from
# the run's transcript — what the tools returned —, so its fields come straight from the sources
# and nothing is written twice; the provider must accept tool messages beside a response schema.
AGENT_REPORT_FROM_ANALYSIS = "analysis"
AGENT_REPORT_FROM_READINGS = "readings"
AGENT_REPORT_SOURCES = (AGENT_REPORT_FROM_ANALYSIS, AGENT_REPORT_FROM_READINGS)

# The report written from the readings: the same rule as a copy — nothing of the model's own. What
# the run read is the task AND what the tools returned: a task may hand the agent what it needs (a map,
# the places earlier runs found), and an agent that answers from it calls no tool. Told
# to use "what the tools returned" alone, such a run reports everything it designated from its task
# as searched in vain.
AGENT_REPORT_FROM_READINGS_INSTRUCTION = (
    "Write the requested report now, from what you read above: the task you were given and what "
    "the tools returned. Use only that: add no figure or source of your own, give every value "
    "where you read it, and leave a field empty when nothing you read states it."
)

# The correction round a report check opens: what it found in the report's fields.
AGENT_REPORT_CORRECTION_INSTRUCTION = (
    "A check of your report against its sources found the points below wrong. Re-read what you "
    "need with the tools: each point is corrected from the source, or left out when the source "
    "does not support it. The report is then written again."
)

# The correction round's message: what the check found, the analysis rewritten from it.
AGENT_CORRECTION_INSTRUCTION = (
    "A check of your analysis against its sources found the points below wrong. Re-read what you "
    "need, then write your complete analysis again: correct each point from the source, or "
    "remove it when the source does not support it. Change nothing else."
)

# What an unsourced figure is told (AgentDefinition.figures_check): a figure found nowhere in the run.
AGENT_UNSOURCED_FIGURE = (
    "this figure is in none of the run's readings, calculations or task: take it from a reading, "
    "compute it with calculate from figures read, or remove it"
)

# Said when the check itself could not run: the analysis stands, unchecked.
AGENT_ANALYSIS_UNCHECKED = "The analysis could not be checked against its sources."

# Upper bound, in seconds, of the trace's closing write: shielded from a cancellation, so a
# store that stops answering would hold the caller forever without it.
AGENT_TRACE_CLOSE_TIMEOUT = 10
