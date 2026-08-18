"""
Discount entity definitions.

This module defines:
- LicenseDiscountUnit: how a discount's value is expressed
- LicenseDiscountGrant: how a discount is obtained (automatically, or by an administrator)
- LicenseDiscount: a reduction the catalogue can offer
- SubscriptionDiscount: the discount a subscription currently benefits from
"""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.apps.licensing.consts import PERCENT_UNIT
from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class LicenseDiscountUnit(ParametricEntity):
    """
    How a discount's value is expressed.

    Only PERCENT is shipped. A fixed amount would carry a currency, and a
    discount would then have to be restated for each currency a price exists in;
    a percentage applies to all of them. The unit is a reference of its own so
    that adding one later does not mean reinterpreting the values already
    granted.

    Attributes:
        id: Unit identifier ("PERCENT")
        description: Human-readable description
        enabled: If False, no new discount can be declared with this unit
    """
    __tablename__ = "license_discount_unit"


@register_entity()
class LicenseDiscountGrant(ParametricEntity):
    """
    How a discount is obtained.

    Only one way is shipped: MANUAL, meaning the discount is claimed — someone
    ticks it when subscribing, and its identifier travels with the subscription.

    The reference exists as an entity of its own so that another way — a discount
    applying to whoever subscribes while it is enabled, for instance — can be
    added without reinterpreting what was granted before it existed.

    Attributes:
        id: Grant identifier ("MANUAL")
        description: Human-readable description
        enabled: If False, no new discount can be declared with this grant
    """
    __tablename__ = "license_discount_grant"


@register_entity()
class LicenseDiscount(ParametricEntity):
    """
    A reduction the catalogue can offer on a subscription's price.

    A discount reduces what a client owes without touching the catalogue: prices
    are immutable and shared by every subscriber, so a negotiated or promotional
    reduction cannot be expressed as a price of its own.

    What entitles a client to a discount is not checked here: the conditions are
    commercial, they are agreed outside the application, and the platform records
    what was granted rather than deciding it.

    Attributes:
        id: Discount identifier (e.g., "WELCOME", "PARTNER")
        value: How much is taken off the price, read in the unit below
        unit_id: Reference to how the value is expressed
        grant_id: Reference to how the discount is obtained
        description: Human-readable description, shown when offering the discount
        enabled: If False, the discount can no longer be granted. Subscriptions
                 already benefiting from it keep it until their term
    """
    __tablename__ = "license_discount"

    value: Mapped[int] = mapped_column(
        nullable=False,
        comment="How much is taken off the price, read in the discount's unit"
    )
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("license_discount_unit.id", ondelete="RESTRICT"),
        default=PERCENT_UNIT,
        nullable=False,
        index=True
    )
    grant_id: Mapped[str] = mapped_column(
        ForeignKey("license_discount_grant.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    @declared_attr
    def unit(self):
        """How this discount's value is expressed."""
        return relationship("license_discount_unit", lazy="selectin")

    @declared_attr
    def grant(self):
        """How this discount is obtained."""
        return relationship("license_discount_grant", lazy="selectin")


@register_entity()
class SubscriptionDiscount(Entity):
    """
    The discount a subscription currently benefits from.

    One row per subscription at most: discounts do not stack. Stacking would
    require settling the order they apply in, the rounding between them and a
    floor to stay above zero — three questions no business need has raised.

    The row carries the value **as granted**, unit included, not a reference to
    read back from the discount: catalogue prices are immutable so that a
    subscriber keeps what they subscribed to, and a discount recomputed at read
    time would break that promise the day its value is revised.

    It carries no dates either. A discount granted against a commitment runs
    until its term, which the subscription already knows; duplicating that date
    would only create a second truth to keep in sync. The row is removed when
    the commitment reaches its term, which is what makes the renewal happen at
    the catalogue price.

    Granted on a subscription with no commitment, it has no term to die with and
    stands until it is revoked. That is a consequence of tying the discount to
    the commitment, not an oversight: an offer sold without commitment has no
    date to hang a reduction on.

    Attributes:
        subscription_id: Reference to the subscription benefiting from it
        discount_id: Reference to the granted discount
        value: Value as granted, frozen at that moment
        unit_id: Unit the value is read in, frozen with it
    """
    __tablename__ = "subscription_discount"

    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("subscription.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    discount_id: Mapped[str] = mapped_column(
        ForeignKey("license_discount.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    value: Mapped[int] = mapped_column(
        nullable=False,
        comment="Value as granted, frozen at that moment"
    )
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("license_discount_unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    @declared_attr
    def subscription(self):
        """Subscription benefiting from the discount."""
        return relationship("subscription", lazy="selectin")

    @declared_attr
    def discount(self):
        """Granted discount."""
        return relationship("license_discount", lazy="selectin")

    @declared_attr
    def unit(self):
        """Unit the granted value is read in."""
        return relationship("license_discount_unit", lazy="selectin")

    __table_args__ = (
        # Discounts do not stack: the row is the active discount, replaced rather
        # than accumulated.
        UniqueConstraint("subscription_id", name="uq_subscription_discount_subscription"),
    )
