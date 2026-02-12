from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship, backref

from lys.core.entities import Entity
from lys.core.registries import register_entity
from lys.core.utils.datetime import now_utc


@register_entity()
class UserSSOLink(Entity):
    """
    Links a user account to an external SSO provider identity.

    Each user can have at most one link per provider.
    Each external identity can only be linked to one user.
    """
    __tablename__ = "user_sso_link"

    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="User reference"
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="SSO provider identifier (e.g. microsoft, google)"
    )
    external_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User ID from the SSO provider (OID for Microsoft)"
    )
    external_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email address from the SSO provider"
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=now_utc,
        comment="Timestamp when the SSO link was created"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_sso_link_user_provider"),
        UniqueConstraint("provider", "external_user_id", name="uq_user_sso_link_provider_external_id"),
    )

    @declared_attr
    def user(cls):
        return relationship(
            "user",
            backref=backref("sso_links", lazy="noload"),
            foreign_keys=[cls.user_id],
            uselist=False,
            lazy="selectin"
        )

    def accessing_users(self) -> list[str]:
        """The user who owns this SSO link can access it."""
        return [self.user_id]

    def accessing_organizations(self) -> dict[str, list[str]]:
        """SSO links are user-scoped, no organization access."""
        return {}