"""
AI Conversation constants.
"""

from enum import Enum


# Purpose for conversation-based AI interactions
AI_PURPOSE_CHATBOT = "chatbot"

# GraphQL node type a conversation GlobalID carries. Clients only ever handle GlobalIDs,
# so the chat stream hands one out under this type and the entry points decode it back.
AI_CONVERSATION_NODE_NAME = "AIConversationNode"

# Length of the fallback display title, mirroring the AIConversation.title column so an
# untitled conversation reads like a titled one in a listing. Also caps a generated title,
# which the column would otherwise reject.
DISPLAY_TITLE_MAX_LENGTH = 255

# Messages returned by a conversation search. Enough to reconstruct a thread, few enough
# that the results do not themselves crowd out the context the search was meant to save.
DEFAULT_SEARCH_RESULTS = 5

AI_PURPOSE_EMBEDDING = "embedding"

# Mistral's embeddings endpoint accepts at most 128 inputs and 16384 tokens per request.
# Both are held under with margin, and both matter: a batch can breach the count on short
# messages and the token budget on long ones.
EMBEDDING_MAX_BATCH = 100
# Characters, not tokens, because counting tokens would mean shipping the model's
# tokenizer. Three characters per token is pessimistic for French, so the real request
# stays well under the limit.
EMBEDDING_MAX_BATCH_CHARS = 36_000
# A single text is truncated rather than dropped: a message long enough to breach the
# per-input limit is a pasted document, whose opening carries what it is about.
EMBEDDING_MAX_CHARS = 8_000

# Width of the stored embedding vectors, fixed by the model that produces them
# (mistral-embed outputs 1024). A column width is part of the schema, so changing it
# is a migration and a re-embedding, not a setting - hence the constant rather than a
# configuration value.
EMBEDDING_DIMENSIONS = 1024

# Cosine distance beyond which a message is not considered a semantic match.
# Unlike the lexical sources, a vector search always returns its N nearest rows: with
# no ceiling, an unrelated query still votes, and the merge surfaces whatever the
# conversation happens to contain. Measured on real content: a query on the subject
# sits near 0.21, an adjacent one near 0.26, an unrelated sentence at 0.34 and up.
MAX_SEMANTIC_DISTANCE = 0.30

# Trigram match floor, mirroring PostgreSQL's own word_similarity_threshold default.
# Measured on real content: an unaccented spelling scores 1.0, a plausible typo ~0.65,
# an unrelated word ~0.08 - so 0.6 separates a near-miss from noise.
TRIGRAM_SIMILARITY_THRESHOLD = 0.6

# Reciprocal rank fusion constant, the value the method is usually published with. It
# flattens the gap between the top ranks, so one source cannot win on its first result
# alone when the other disagrees.
RANK_FUSION_CONSTANT = 60

# Conversation titling. Runs once, off the request path, from the opening user message:
# the answer adds little to a label and waiting for it would only delay the title. Until
# it lands, a listing falls back to the truncated opening message, so a failure degrades
# instead of leaving an empty row.
AI_PURPOSE_CONVERSATION_TITLE = "conversation_title"

DEFAULT_TITLE_PROMPT = (
    "You label a conversation from its opening message. Produce a short title, at most a "
    "handful of words, naming the subject the user is asking about. Write it in the same "
    "language as the message. Output only the title: no quotes, no punctuation at the end, "
    "no preamble."
)

# Default English section headers for system-prompt segments. lys stays locale-neutral;
# a consumer can override these via the ai plugin config (chatbot.dynamic_context_header /
# chatbot.summary_header), e.g. to localise them for the conversation language.
DEFAULT_DYNAMIC_CONTEXT_HEADER = "## Dynamic context"
DEFAULT_SUMMARY_HEADER = (
    "## Previous conversation summary\n"
    "This condenses the earlier exchange. What it leaves out is not lost: search_conversation "
    "retrieves the messages themselves, when that tool is available to you."
)


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