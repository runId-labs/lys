"""
Subscription entity definitions.

This module defines:
- Subscription: Client subscription to a license plan version
- subscription_user: Association table linking subscriptions to users
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.apps.licensing.modules.subscription.prorata import subtract_months
from lys.apps.licensing.consts import MANUAL_BILLING, PROVIDER_BILLING
from lys.core.entities import Entity, ParametricEntity
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
class LicenseBillingMode(ParametricEntity):
    """
    How a subscription is collected.

    This is a routing value, not a payment provider: it says whether collection
    goes through the configured provider or is handled outside the application,
    typically by invoicing. Which provider is used is a matter of configuration.

    Why two modes
    -------------
    An application usually launches before its payment integration is ready.
    Clients are then placed on their plan by an administrator and invoiced by
    other means, while entitlements, commitment and renewal already work: those
    depend on the plan and its price, never on how the money is collected.

    Migration to a provider
    -----------------------
    Adopting a provider is a per-client move, not a global switch: the client
    goes through checkout, and the first successful payment sets the mode to
    PROVIDER. Nothing is switched beforehand.

    The mode is therefore always true, which is what billing teams read to know
    who to invoice: MANUAL means nothing collects automatically, PROVIDER means
    the provider does. Flipping it in advance would mark a client as collected
    while nothing collects, and the invoicing would stop for a subscription
    nobody is charging.

    The reverse move is refused while the provider still collects: switching the
    mode does not stop the provider subscription, and every provider branch is
    skipped once manual, so the client would be charged and invoiced at the same
    time, and a later cancellation would no longer stop the collection. Billing a
    collected subscription manually therefore means cancelling it first.

    A period can be both invoiced and charged during the move. Nothing here can
    prevent it: whether to switch at a period boundary is an operational choice.

    Every mode is backed by code. Adding a value without the service able to
    honour it must fail loudly rather than silently collect nothing.

    Attributes:
        id: Mode identifier ("MANUAL", "PROVIDER")
        description: Human-readable name, shown when choosing how to bill
        enabled: If False, the mode cannot be used for new subscriptions
    """
    __tablename__ = "license_billing_mode"

    def accessing_users(self) -> list[str]:
        """Users who can access this billing mode."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this billing mode."""
        return {}


@register_entity()
class Subscription(Entity):
    """
    Client subscription to a license plan version.

    Each client has at most one active subscription at a time.
    All billing details (status, period, price) are managed by the payment provider.

    Attributes:
        client_id: The subscribing client
        plan_version_id: The plan version subscribed to
        plan_version_price_id: The exact price subscribed to, which carries the
                               periodicity, the currency and the amount agreed
                               upon. NULL on free subscriptions, which have no
                               price at all
        billing_mode_id: How the subscription is collected: through the provider
                         or outside the application
        provider_subscription_id: Payment provider subscription ID, only set when
                                  billed through the provider
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
    plan_version_price_id: Mapped[str | None] = mapped_column(
        ForeignKey("license_plan_version_price.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Price subscribed to; NULL on free subscriptions"
    )

    billing_mode_id: Mapped[str] = mapped_column(
        ForeignKey("license_billing_mode.id", ondelete="RESTRICT"),
        default=PROVIDER_BILLING,
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
    commitment_end_date: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="End of the contractual commitment; NULL when not committed"
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
    def billing_mode(self):
        """How this subscription is collected."""
        return relationship("license_billing_mode", lazy="selectin")

    @declared_attr
    def plan_version_price(self):
        """Price subscribed to, or None on a free subscription."""
        return relationship("license_plan_version_price", lazy="selectin")

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
        """
        Returns True if nothing is owed for this subscription.

        This is a property of the plan subscribed to, not of the way it is
        collected: a paid subscription billed by invoice has no provider
        subscription and is not free.
        """
        return self.plan_version_price_id is None

    @property
    def is_manually_billed(self) -> bool:
        """Returns True if collection happens outside the application."""
        return self.billing_mode_id == MANUAL_BILLING

    @property
    def is_committed(self) -> bool:
        """
        Returns True if the client is still bound by a commitment.

        While committed, the subscription cannot be downgraded or cancelled
        before the commitment end date.
        """
        if self.commitment_end_date is None:
            return False

        end_date = self.commitment_end_date
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=UTC)

        return end_date > datetime.now(UTC)

    @property
    def effective_change_date(self):
        """
        Date a scheduled plan change takes effect.

        A commitment outlives the current billing period, so a change requested
        while committed only applies at the end of the commitment.
        """
        if self.is_committed:
            return self.commitment_end_date
        return self.current_period_end

    @property
    def notice_deadline(self):
        """
        Last date a denunciation is accepted for the current term.

        Returns None when the subscription is not committed, or when the
        commitment requires no notice: the term itself is then the deadline.
        """
        if not self.is_committed:
            return None

        commitment = (
            self.plan_version_price.commitment
            if self.plan_version_price is not None else None
        )
        if commitment is None or not commitment.notice_months:
            return self.commitment_end_date

        return subtract_months(self.commitment_end_date, commitment.notice_months)

    @property
    def is_within_notice_period(self) -> bool:
        """
        Returns True if a denunciation can still be received for this term.

        Past the deadline the commitment is tacitly renewed, and the client has
        to wait for the next notice window.
        """
        deadline = self.notice_deadline
        if deadline is None:
            return True

        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)

        return datetime.now(UTC) <= deadline

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        """Filter subscriptions by client organization access."""
        client_ids = organization_id_dict.get("client", [])
        if client_ids:
            return stmt, [cls.client_id.in_(client_ids)]
        return stmt, []

    def accessing_users(self) -> list[str]:
        """Users who can access this subscription."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this subscription."""
        return {
            "client": [self.client_id] if self.client_id else []
        }
