"""
AI Conversation entities.

This module provides entities for storing AI conversations with per-message
feedback and metrics, supporting analytics and fine-tuning data export.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey, Integer, Uuid, JSON, DateTime
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr

from lys.apps.ai.modules.conversation.consts import EMBEDDING_DIMENSIONS
from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class AIConversation(Entity):
    """
    A conversation session with the AI.

    Each conversation belongs to a user and has a purpose (e.g., "chatbot", "analysis")
    that determines which AI endpoint configuration is used.
    """

    __tablename__ = "ai_conversation"

    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        nullable=False,
        index=True,
        comment="Reference to user (soft FK - no constraint for microservices)",
    )
    client_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False),
        nullable=True,
        index=True,
        comment=(
            "Optional tenant/client reference (soft FK - no constraint for microservices), "
            "stamped at creation time by consumers that scope conversations to a tenant"
        ),
    )
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Timezone-aware like every other timestamp in the framework: the column records an
    # instant, and a naive one cannot be compared across the deployments that read it.
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    @declared_attr
    def messages(cls):
        return relationship(
            "ai_message",
            back_populates="conversation",
            order_by="ai_message.created_at",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    @declared_attr
    def summaries(cls):
        # Not selectin-loaded: summaries are queried directly (latest completed row),
        # never needed eagerly on every conversation fetch.
        return relationship(
            "ai_conversation_summary",
            back_populates="conversation",
            cascade="all, delete-orphan",
        )

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        return stmt, [cls.user_id == user_id]


@register_entity()
class AIMessage(Entity):
    """
    A single message in a conversation.

    Stores the message content, role, and for assistant messages,
    includes metrics like token usage and latency.
    """

    __tablename__ = "ai_message"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The answer's spoken rendition, as produced by the model inside the
    # spoken-block tags (chatbot.spoken_block). The written rendition above is
    # stored WITHOUT the blocks: history, search and compaction never see the
    # tags, and the model is never fed its own spoken text on a later turn.
    # Null when the feature is off, or when the model wrote no block — the
    # drift the fallback voice and the corpus accounting both key on.
    spoken_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # For tool calls (role=assistant)
    tool_calls: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)

    # For tool results (role=tool)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # What varied for this turn, recorded because it cannot be reconstructed afterwards:
    # the system prompt is assembled per turn and never persisted, the caller's page context
    # is transient, and the offered tool list depends on rights held at that moment. Written
    # on the user row - one per turn, whereas an agent loop writes several assistant rows.
    #
    # Framework-defined keys: "options" (endpoint options actually used), "tools" (names
    # offered to the model, never their schemas - those are large and versioned elsewhere),
    # "volatile_context" (the uncached system segment as sent). "page_context" keeps the
    # framework's own envelope - page name and params - while the params themselves are
    # stored as received: their keys are the consumer's vocabulary, never read here.
    request_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # The prompt version that produced this message. Points to an immutable row in
    # ai_prompt_version, so any past response can be traced back to the exact system
    # prompt that generated it. Written on the user row for the same reason as
    # request_context: one per turn, on the line that starts it.
    prompt_version_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("ai_prompt_version.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    @declared_attr
    def prompt_version(cls):
        return relationship("ai_prompt_version", lazy="selectin")

    # Metrics (role=assistant only)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Prompt-cache usage (provider-agnostic; Anthropic cache_read/cache_creation input
    # tokens, currently dropped by the providers). Lets us measure cache effectiveness.
    cache_read_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Deliberately measures two different things, one per call path, because neither has a
    # counterpart on the other: the non-streaming path times a complete request/response,
    # the streaming path times up to the LAST token. Tool execution is excluded from both.
    # Compare within a path, never across.
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Full-text search over the message content. Filled off the request path, so a message
    # is searchable shortly after it is written rather than at write time; a row whose
    # indexing has not run - or predates the feature - simply does not match, it never
    # breaks a search.
    #
    # The configuration is stored beside the vector because a tsvector cannot be read
    # without it: lexemes are stemmed by a given configuration, and a query stemmed by
    # another one will not match them. Detected per message rather than set globally,
    # since two users of the same instance legitimately write in two languages.
    # Declared as Text with a PostgreSQL variant rather than TSVECTOR outright: the raw
    # type compiles on no other dialect, and the framework's own integration tests build
    # their schema on SQLite. The column is a plain TEXT there - searching it is a
    # PostgreSQL matter either way, so nothing is lost that SQLite could have offered.
    text_search_vector: Mapped[Optional[str]] = mapped_column(
        Text().with_variant(TSVECTOR(), "postgresql"), nullable=True
    )
    text_search_config: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Semantic search over the message content, complementing the lexical one: full-text
    # and trigrams both match on how a thing was written, and miss it entirely when the
    # same idea comes back in other words.
    #
    # The model is stored beside the vector for the same reason the text search
    # configuration is: vectors from two models live in unrelated spaces, and comparing
    # across them returns confident nonsense rather than an error. Rows embedded with a
    # retired model stay readable, and are re-embedded rather than silently mismatched.
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    @declared_attr
    def conversation(cls):
        return relationship("ai_conversation", back_populates="messages")

    @declared_attr
    def feedback(cls):
        return relationship(
            "ai_message_feedback",
            back_populates="message",
            uselist=False,
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id: str):
        # Ownership lives on the parent conversation: a message belongs to the user its
        # conversation belongs to. Goes through the mapped relationship rather than the
        # entity class, which lys rebuilds through its registry - a direct class reference
        # compiles to unresolved columns. `has()` emits a correlated EXISTS, leaving a
        # caller's own joins and row count untouched.
        return stmt, [cls.conversation.has(user_id=user_id)]


@register_entity()
class AIMessageFeedback(Entity):
    """
    User feedback on an AI message.

    Simple rating + comment for beta testing.
    """

    __tablename__ = "ai_message_feedback"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("ai_message.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        nullable=False,
        index=True,
        comment="Reference to user (soft FK - no constraint for microservices)",
    )
    rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @declared_attr
    def message(cls):
        return relationship("ai_message", back_populates="feedback")

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}


@register_entity()
class AIConversationSummary(Entity):
    """
    A rolling compaction summary of older messages in a conversation.

    When a conversation's reconstructed prompt grows past a token threshold, the
    messages older than the verbatim window are condensed into a summary so the
    prompt stays bounded. Each compaction event is one immutable row: it records
    the boundary message it covers (`through_message_id` - the verbatim window is
    the messages after it), the model used, and the token cost of the summarization
    call itself. The current summary for a conversation is the latest row with
    `completed=True`. The row is created uncompleted when a background task is
    enqueued and filled when it finishes; `completed=False` therefore doubles as a
    concurrency guard against enqueuing two summarizations for the same conversation.
    """

    __tablename__ = "ai_conversation_summary"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    through_message_id: Mapped[str] = mapped_column(
        ForeignKey("ai_message.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Cost tracking of the summarization call itself (provider-agnostic).
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # False while the background task is in flight (concurrency guard); True once filled.
    completed: Mapped[bool] = mapped_column(default=False, nullable=False)

    @declared_attr
    def conversation(cls):
        return relationship("ai_conversation", back_populates="summaries")

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}
