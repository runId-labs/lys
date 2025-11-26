from datetime import datetime
from typing import List

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr

from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class AIConversation(Entity):
    """
    Entity for storing AI conversation history.

    Each conversation belongs to a user and contains the full message history
    including user messages, assistant responses, and tool calls/results.
    """
    __tablename__ = "ai_conversations"
    __abstract__ = False

    # Owner of the conversation
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)

    # Conversation title (auto-generated or user-defined)
    title: Mapped[str] = mapped_column(Text, nullable=True)

    # Message history as JSON array
    # Format: [{"role": "user/assistant/tool", "content": "...", "tool_calls": [...]}]
    messages: Mapped[List[dict]] = mapped_column(JSONB, default=list)

    # Metadata
    message_count: Mapped[int] = mapped_column(default=0)
    last_message_at: Mapped[datetime] = mapped_column(nullable=True)

    # Relationships
    @declared_attr
    def user(cls):
        return relationship("user", lazy="selectin")

    def accessing_users(self):
        """Only the owner can access the conversation."""
        return [self.user] if self.user else []

    def accessing_organizations(self):
        """No organization-based access for conversations."""
        return {}