"""
AI Conversation entities.

This module provides entities for storing AI conversations with per-message
feedback and metrics, supporting analytics and fine-tuning data export.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Text, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr

from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class AIConversation(Entity):
    """
    A conversation session with the AI.

    Each conversation belongs to a user and has a purpose (e.g., "chatbot", "analysis")
    that determines which AI endpoint configuration is used.
    """

    __tablename__ = "ai_conversations"

    user_id: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
        comment="Reference to user (soft FK - no constraint for microservices)",
    )
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    @declared_attr
    def messages(cls):
        return relationship(
            "ai_messages",
            back_populates="conversation",
            order_by="ai_messages.created_at",
            cascade="all, delete-orphan",
            lazy="selectin",
        )

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}


@register_entity()
class AIMessage(Entity):
    """
    A single message in a conversation.

    Stores the message content, role, and for assistant messages,
    includes metrics like token usage and latency.
    """

    __tablename__ = "ai_messages"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # For tool calls (role=assistant)
    tool_calls: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)

    # For tool results (role=tool)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metrics (role=assistant only)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    @declared_attr
    def conversation(cls):
        return relationship("ai_conversations", back_populates="messages")

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


@register_entity()
class AIMessageFeedback(Entity):
    """
    User feedback on an AI message.

    Simple rating + comment for beta testing.
    """

    __tablename__ = "ai_message_feedback"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
        comment="Reference to user (soft FK - no constraint for microservices)",
    )
    rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @declared_attr
    def message(cls):
        return relationship("ai_messages", back_populates="feedback")

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}