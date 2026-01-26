"""
Notification entities extension for user_role app.

Extends the base NotificationType with roles relationship via the
notification_type_role association table.
"""
from sqlalchemy import Table, Column, String, ForeignKey, DateTime, func
from sqlalchemy.orm import declared_attr, relationship

from lys.core.entities import ParametricEntity
from lys.core.managers.database import Base
from lys.core.registries import register_entity


# Association table for NotificationType <-> Role many-to-many
notification_type_role = Table(
    "notification_type_role",
    Base.metadata,
    Column(
        "notification_type_id",
        String,
        ForeignKey("notification_type.id", ondelete="CASCADE"),
        primary_key=True
    ),
    Column(
        "role_id",
        String,
        ForeignKey("role.id", ondelete="CASCADE"),
        primary_key=True
    ),
    Column(
        "created_at",
        DateTime,
        nullable=False,
        server_default=func.now()
    ),
)


@register_entity()
class NotificationType(ParametricEntity):
    """
    Extended NotificationType with roles relationship.

    Overrides the base NotificationType from lys.apps.base to add:
    - roles: Many-to-many relationship to Role via notification_type_role table

    Attributes:
        id: Unique identifier (e.g., "ORDER_CREATED")
        name: Human-readable name
        roles: Roles that should receive this notification type
    """
    __tablename__ = "notification_type"

    @declared_attr
    def roles(cls):
        """Many-to-many relationship to Role via association table."""
        return relationship(
            "role",
            secondary=notification_type_role,
            lazy="selectin"
        )