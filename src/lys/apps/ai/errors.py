"""
AI app errors.
"""

# A chat turn carries exactly one input: a user message, or the answers to the calls the
# last turn left open — never both, never neither.
INVALID_CHAT_INPUT = (400, "INVALID_CHAT_INPUT")

# The answers posted for open tool calls do not match the calls the server left open:
# unknown or already answered ids, a call of a tool the user does not answer, or an
# incomplete set — every open call of the turn is answered at once.
INVALID_TOOL_ANSWERS = (400, "INVALID_TOOL_ANSWERS")

# An agent run needs the user's own token: the agent reads with the user's rights, never
# with a service identity that would read more than the user may.
AGENT_REQUIRES_USER_TOKEN = (403, "AGENT_REQUIRES_USER_TOKEN")

# The run a follow-up names is not one the caller may continue: unknown, another user's, another
# agent's or another client's — one answer for all, nothing told of a run that is not the caller's.
AGENT_RUN_NOT_FOUND = (404, "AGENT_RUN_NOT_FOUND")

# The run exists and is the caller's, but cannot be followed up: it did not succeed, or ended too
# long ago (AgentDefinition.continuation_ttl).
AGENT_RUN_NOT_CONTINUABLE = (409, "AGENT_RUN_NOT_CONTINUABLE")
