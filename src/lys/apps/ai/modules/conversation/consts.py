"""
AI Conversation constants.
"""

from enum import Enum


# Purpose for conversation-based AI interactions
AI_PURPOSE_CHATBOT = "chatbot"

# Default English section headers for system-prompt segments. lys stays locale-neutral;
# a consumer can override these via the ai plugin config (chatbot.dynamic_context_header /
# chatbot.summary_header), e.g. to localise them for the conversation language.
DEFAULT_DYNAMIC_CONTEXT_HEADER = "## Dynamic context"
DEFAULT_SUMMARY_HEADER = "## Previous conversation summary"


# Conversation compaction. Defaults are locale-neutral and overridable via the ai plugin
# config: the `conversation_summary` endpoint (provider / model / system_prompt) and
# `chatbot.compaction.{token_threshold, window_messages}`.
AI_PURPOSE_CONVERSATION_SUMMARY = "conversation_summary"

# Compact when the last turn's reconstructed prompt (input + cache read + cache write
# tokens) exceeds this, leaving margin under the model context window.
DEFAULT_COMPACTION_TOKEN_THRESHOLD = 120000
# Recent messages kept verbatim; older ones are represented by the rolling summary.
DEFAULT_COMPACTION_WINDOW_MESSAGES = 12
# A pending (completed=False) summary older than this is treated as stale — its worker is
# assumed dead — so the concurrency guard ignores it and a new compaction can be enqueued.
DEFAULT_COMPACTION_PENDING_TTL_SECONDS = 600

DEFAULT_COMPACTION_PROMPT = (
    "You maintain a running summary of the earlier part of an ongoing conversation so it "
    "fits a limited context window. Given the prior summary (if any) and the next batch of "
    "messages, produce one updated summary that preserves every decision-relevant fact, "
    "open question, and user intent. Attribute each fact to the specific subject it concerns "
    "(entity, period, topic) so distinct subjects are never conflated. Keep names, figures "
    "and identifiers verbatim. Write the summary in the same language as the conversation. "
    "Output only the summary, with no preamble."
)


class AIMessageRole(str, Enum):
    """Role of a message in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AIFeedbackRating(str, Enum):
    """Rating for feedback on a message."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"