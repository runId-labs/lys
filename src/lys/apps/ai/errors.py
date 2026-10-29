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
