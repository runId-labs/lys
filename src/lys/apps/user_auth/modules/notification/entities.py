"""
Notification system entities.

This module defines the database models for the notification system:

- NotificationType: Parametric entity defining types of notifications
- NotificationBatch: Represents a single triggering event that generates notifications
- Notification: Individual notification per user

Extensions:
- user_role app extends NotificationType with roles relationship
- organization app extends NotificationBatch with organization_data

Flow:
1. An event triggers a notification (e.g., "new order created")
2. System creates a NotificationBatch with the event data
3. System resolves recipients: users with roles linked to the NotificationType + trigger user
4. System creates individual Notification for each recipient
5. Signal NOTIFICATION_CREATED is published to each user's channel
"""
from typing import List

from sqlalchemy import ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class NotificationType(ParametricEntity):
    """
    Base parametric entity defining notification types.

    Each type represents a category of notification (e.g., "ORDER_CREATED", "USER_INVITED").

    Note: This base class has no roles relationship. The user_role app extends this
    entity with the roles relationship via notification_type_role association table.

    Attributes:
        id: Unique identifier (e.g., "ORDER_CREATED")
        name: Human-readable name
    """
    __tablename__ = "notification_type"


@register_entity()
class NotificationBatch(Entity):
    """
    Base entity representing a single triggering event that generates notifications.

    When an event occurs (e.g., order created), a batch is created to group
    all individual notifications sent to recipients. This avoids data duplication
    and allows tracking who received a specific notification event.

    Note: The organization_data attribute is defined in the organization app
    which extends NotificationBatch for multi-tenant scoping.

    Attributes:
        type_id: FK to NotificationType
        triggered_by_user_id: FK to user who triggered the notification
        data: JSON payload with event-specific data for frontend formatting
        notifications: Individual notifications sent to each recipient
    """
    __tablename__ = "notification_batch"

    type_id: Mapped[str] = mapped_column(
        ForeignKey("notification_type.id"),
        nullable=False,
        index=True,
        comment="FK to notification_type"
    )
    triggered_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who triggered the notification"
    )
    data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Event data for frontend formatting (e.g., order_id, user_name)"
    )

    @declared_attr
    def type(cls):
        """Relationship to NotificationType."""
        return relationship("notification_type", lazy="selectin")

    @declared_attr
    def notifications(cls) -> Mapped[List["Notification"]]:
        """Individual notifications created from this batch."""
        return relationship(
            "notification",
            back_populates="batch",
            cascade="all, delete-orphan",
            lazy="selectin"
        )

    def accessing_users(self) -> list[str]:
        return [self.triggered_by_user_id] if self.triggered_by_user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}


@register_entity()
class Notification(Entity):
    """
    Individual notification for a specific user.

    Each notification belongs to a NotificationBatch and represents
    one user's copy of the notification. Users can mark their own
    notifications as read independently.

    Attributes:
        batch_id: FK to NotificationBatch (contains type and data)
        user_id: FK to recipient user
        is_read: Whether the user has read this notification
    """
    __tablename__ = "notification"

    batch_id: Mapped[str] = mapped_column(
        ForeignKey("notification_batch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to notification_batch"
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Recipient user"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Whether the notification has been read"
    )

    @declared_attr
    def batch(cls):
        """Back reference to the parent NotificationBatch."""
        return relationship("notification_batch", back_populates="notifications")

    def accessing_users(self) -> list[str]:
        return [self.user_id]

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}