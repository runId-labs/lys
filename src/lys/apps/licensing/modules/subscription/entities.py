"""
Subscription entity definitions.

This module defines:
- Subscription: Client subscription to a license plan version
- subscription_user: Association table linking subscriptions to client users
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Table, func
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.core.entities import Entity
from lys.core.managers.database import Base
from lys.core.registries import register_entity


if TYPE_CHECKING:
    from lys.apps.licensing.modules.plan.entities import LicensePlan, LicensePlanVersion
    from lys.apps.organization.modules.client.entities import Client
    from lys.apps.organization.modules.client_user.entities import ClientUser


# Association table for subscription users
subscription_user = Table(
    "subscription_user",
    Base.metadata,
    Column("subscription_id", ForeignKey("subscription.id", ondelete="CASCADE"), primary_key=True),
    Column("client_user_id", ForeignKey("client_user.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


@register_entity()
class Subscription(Entity):
    """
    Client subscription to a license plan version.

    Each client has at most one active subscription at a time.
    All billing details (status, period, price) are managed in Stripe.

    Attributes:
        client_id: The subscribing client
        plan_version_id: The plan version subscribed to
        stripe_subscription_id: Stripe Subscription ID for billing management (NULL for free plans)
        pending_plan_version_id: Plan version to switch to at period end (for scheduled downgrades)
    """
    __tablename__ = "subscription"

    client_id: Mapped[str] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"),
        index=True
    )
    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("license_plan_version.id", ondelete="RESTRICT"),
        index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        nullable=True,
        unique=True
    )

    # Pending downgrade (applied at billing period end)
    pending_plan_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("license_plan_version.id", ondelete="SET NULL"),
        nullable=True
    )

    @declared_attr
    def client(self):
        """Subscribing client."""
        return relationship("client", lazy="selectin")

    @declared_attr
    def plan_version(self):
        """Current plan version."""
        return relationship(
            "license_plan_version",
            foreign_keys=[self.plan_version_id],
            lazy="selectin"
        )

    @declared_attr
    def pending_plan_version(self):
        """Pending plan version for scheduled downgrade."""
        return relationship(
            "license_plan_version",
            foreign_keys=[self.pending_plan_version_id],
            lazy="selectin"
        )

    @declared_attr
    def users(self):
        """Users associated with this subscription (consuming license seats)."""
        return relationship(
            "client_user",
            secondary=subscription_user,
            lazy="selectin"
        )

    @property
    def plan(self) -> "LicensePlan":
        """Returns the license plan."""
        return self.plan_version.plan

    @property
    def has_pending_downgrade(self) -> bool:
        """Returns True if a downgrade is scheduled."""
        return self.pending_plan_version_id is not None
