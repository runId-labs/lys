"""
Subscription entity definitions.

This module defines:
- Subscription: Client subscription to a license plan version
- subscription_user: Association table linking subscriptions to users
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.core.entities import Entity
from lys.core.managers.database import Base
from lys.core.registries import register_entity


if TYPE_CHECKING:
    from lys.apps.licensing.modules.plan.entities import LicensePlan


# Association table for subscription users
subscription_user = Table(
    "subscription_user",
    Base.metadata,
    Column("subscription_id", ForeignKey("subscription.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


@register_entity()
class Subscription(Entity):
    """
    Client subscription to a license plan version.

    Each client has at most one active subscription at a time.
    All billing details (status, period, price) are managed by the payment provider.

    Attributes:
        client_id: The subscribing client
        plan_version_id: The plan version subscribed to
        provider_subscription_id: Payment provider subscription ID (NULL for free plans)
        pending_plan_version_id: Plan version to switch to at period end (for scheduled downgrades)
    """

    __tablename__ = "subscription"

    client_id: Mapped[str] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("license_plan_version.id", ondelete="RESTRICT"),
        index=True
    )

    # Payment provider field
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Payment provider subscription ID (Mollie: sub_xxx)"
    )

    # Pending downgrade (applied at billing period end)
    pending_plan_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("license_plan_version.id", ondelete="SET NULL"),
        nullable=True
    )

    # Billing period tracking
    billing_period: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Billing period: monthly or yearly"
    )
    current_period_start: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Start of current billing period"
    )
    current_period_end: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="End of current billing period"
    )
    canceled_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date when subscription was canceled (takes effect at period end)"
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
            "user",
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

    @property
    def is_canceled(self) -> bool:
        """Returns True if subscription is canceled (takes effect at period end)."""
        return self.canceled_at is not None

    @property
    def is_free(self) -> bool:
        """Returns True if on a free plan (no provider subscription)."""
        return self.provider_subscription_id is None

    def accessing_users(self) -> list[str]:
        """Users who can access this subscription."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this subscription."""
        return {
            "client": [self.client_id] if self.client_id else []
        }
