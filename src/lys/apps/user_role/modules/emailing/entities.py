"""
Emailing entities extension for user_role app.

Extends the base EmailingType with roles relationship via the
emailing_type_role association table.
"""
from sqlalchemy import Table, Column, String, ForeignKey, DateTime, func
from sqlalchemy.orm import declared_attr, relationship

from lys.apps.base.modules.emailing.entities import EmailingType as BaseEmailingType
from lys.core.managers.database import Base
from lys.core.registries import register_entity


# Association table for EmailingType <-> Role many-to-many
emailing_type_role = Table(
    "emailing_type_role",
    Base.metadata,
    Column(
        "emailing_type_id",
        String,
        ForeignKey("emailing_type.id", ondelete="CASCADE"),
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
class EmailingType(BaseEmailingType):
    """
    Extended EmailingType with roles relationship.

    Overrides the base EmailingType from lys.apps.base to add:
    - roles: Many-to-many relationship to Role via emailing_type_role table

    Inherits from base EmailingType which provides:
    - subject, template, context_description columns

    Attributes:
        id: Unique identifier (e.g., "LICENSE_GRANTED")
        name: Human-readable name
        subject: Email subject line
        template: Template file name
        context_description: JSON schema describing template context variables
        roles: Roles that should receive this emailing type
    """
    __tablename__ = "emailing_type"

    @declared_attr
    def roles(cls):
        """Many-to-many relationship to Role via association table."""
        return relationship(
            "role",
            secondary=emailing_type_role,
            lazy="selectin"
        )