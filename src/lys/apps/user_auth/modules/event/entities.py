"""
Event system entities.

This module defines the database models for user event preferences:

- UserEventPreference: User-specific channel preferences that override defaults
"""
from sqlalchemy import ForeignKey, String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class UserEventPreference(Entity):
    """
    User-specific preference for event channel delivery.

    Allows users to override the default channel settings for specific events.
    For example, a user might disable email notifications for "FINANCIAL_IMPORT_COMPLETED"
    while keeping the in-app notification enabled.

    Note: Preferences for channels in the "blocked" list cannot be created or modified.
    This is enforced by the EventService.

    Attributes:
        user_id: FK to the user who owns this preference
        event_type: The event type key (e.g., "FINANCIAL_IMPORT_COMPLETED")
        channel: The channel type ("email" or "notification")
        enabled: Whether this channel is enabled for this event
    """
    __tablename__ = "user_event_preference"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this preference"
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Event type key (e.g., FINANCIAL_IMPORT_COMPLETED)"
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Channel type: email or notification"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Whether this channel is enabled for this event"
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "event_type", "channel",
            name="uq_user_event_preference_user_event_channel"
        ),
    )

    def accessing_users(self) -> list[str]:
        """User can only access their own preferences."""
        return [self.user_id]

    def accessing_organizations(self) -> dict[str, list[str]]:
        """No organization-level access."""
        return {}