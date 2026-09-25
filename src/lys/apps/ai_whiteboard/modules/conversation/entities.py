"""
AIConversation extension: the whiteboard a conversation writes to by default.

Extends the entity of ``lys.apps.ai`` rather than carrying the link on the whiteboard
side. A column on the whiteboard would tie it to one conversation forever, and the
point is the opposite: a whiteboard survives the exchange that produced it, and a
later conversation picks it up by pointing at the same row.
"""

from typing import Optional

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from lys.apps.ai.modules.conversation.entities import AIConversation as BaseAIConversation
from lys.core.registries import register_entity


@register_entity()
class AIConversation(BaseAIConversation):
    """
    Extends the base AIConversation from the ai app to add:
        whiteboard_id: the whiteboard this conversation writes to when a tool names none
    """

    __tablename__ = "ai_conversation"
    __table_args__ = {"extend_existing": True}

    whiteboard_id: Mapped[Optional[str]] = mapped_column(
        Uuid(as_uuid=False),
        nullable=True,
        index=True,
        comment=(
            "Whiteboard this conversation writes to by default (soft FK - no constraint: "
            "ai_conversation must not reference a table that only exists when the "
            "whiteboard app is loaded). Deleting a whiteboard leaves this pointer dangling, "
            "so the service clears it, and the resolution recreates rather than failing"
        ),
    )
