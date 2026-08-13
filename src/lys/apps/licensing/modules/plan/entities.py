"""
License plan entity definitions.

This module defines:
- LicensePlan: Plan types (FREE, STARTER, PRO, ENTERPRISE)
- LicensePlanVersion: Versioned plans for grandfathering
- LicensePlanVersionRule: Association between a version and a rule with its limit value
- LicensePricePeriod: Billing periodicities (MONTHLY, YEARLY, ...)
- LicenseCurrency: Currencies available for pricing (EUR, USD, ...)
- LicensePlanVersionPrice: Price of a version for a given periodicity and currency
"""

from typing import Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.apps.licensing.consts import DEFAULT_CURRENCY
from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class LicensePlan(ParametricEntity):
    """
    License plan type.

    Attributes:
        id: Plan identifier (e.g., "FREE", "STARTER", "PRO", "ENTERPRISE")
        app_id: Application this plan belongs to (for multi-app support)
        client_id: If set, this is a custom plan for a specific client
        description: Human-readable description
        enabled: If False, plan cannot be selected for new subscriptions
                 (existing subscriptions remain active)
    """
    __tablename__ = "license_plan"

    app_id: Mapped[str] = mapped_column(
        ForeignKey("license_application.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    @declared_attr
    def application(self):
        """Application this plan belongs to."""
        return relationship("license_application", lazy="selectin")

    @declared_attr
    def client(self):
        """Client for custom plans (NULL for global plans)."""
        return relationship("client", lazy="selectin")

    @declared_attr
    def versions(self):
        """All versions of this plan."""
        return relationship(
            "license_plan_version",
            back_populates="plan",
            lazy="selectin"
        )

    @property
    def is_custom(self) -> bool:
        """Returns True if this is a custom plan for a specific client."""
        return self.client_id is not None

    @property
    def current_version(self) -> "LicensePlanVersion | None":
        """Returns the current (enabled) version of this plan."""
        for version in self.versions:
            if version.enabled:
                return version
        return None


@register_entity()
class LicensePricePeriod(ParametricEntity):
    """
    Billing periodicity available for plan pricing.

    The interval is expressed in months, which covers every supported billing
    cadence (monthly, quarterly, half-yearly, yearly, biennial) and lets billing
    period boundaries be computed generically, without hardcoding a periodicity
    in the billing code.

    Attributes:
        id: Period identifier (e.g., "MONTHLY", "YEARLY")
        interval_months: Number of months in one billing period
        description: Human-readable description
        enabled: If False, the periodicity cannot be selected for new subscriptions
    """
    __tablename__ = "license_price_period"

    interval_months: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="Number of months in one billing period"
    )

    def accessing_users(self) -> list[str]:
        """Users who can access this price period."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this price period."""
        return {}


@register_entity()
class LicenseCurrency(ParametricEntity):
    """
    Currency available for plan pricing.

    Attributes:
        id: ISO 4217 code, uppercase (e.g., "EUR", "USD", "JPY")
        minor_unit: Number of decimal places of the currency. Amounts are stored
                    in minor units, so this defines how they convert to a
                    displayable value (2 for EUR, 0 for JPY)
        description: Human-readable name
        enabled: If False, the currency cannot be used for new prices
    """
    __tablename__ = "license_currency"

    minor_unit: Mapped[int] = mapped_column(
        default=2,
        nullable=False,
        comment="Number of decimal places of the currency (2 for EUR, 0 for JPY)"
    )

    def to_major_unit(self, amount: int) -> float:
        """
        Convert an amount expressed in minor units to its major unit value.

        Args:
            amount: Amount in minor units (e.g., 4900 for 49.00 EUR)

        Returns:
            Amount in major units (e.g., 49.0)
        """
        return amount / (10 ** self.minor_unit)

    def accessing_users(self) -> list[str]:
        """Users who can access this currency."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this currency."""
        return {}


@register_entity()
class LicensePlanVersion(Entity):
    """
    Version of a license plan.

    Each plan can have multiple versions to support grandfathering:
    existing subscribers keep their version's rules and prices even if the
    plan changes.

    Pricing is held by the associated LicensePlanVersionPrice rows, one per
    (periodicity, currency). A version without any price row is free.

    Attributes:
        plan_id: Reference to the parent plan
        version: Version number (1, 2, 3...)
        enabled: If True, this is the current version for new subscriptions.
                 Only ONE version per plan should be enabled at a time.
    """
    __tablename__ = "license_plan_version"

    plan_id: Mapped[str] = mapped_column(
        ForeignKey("license_plan.id", ondelete="CASCADE"),
        index=True
    )
    version: Mapped[int] = mapped_column(default=1)
    enabled: Mapped[bool] = mapped_column(default=True)

    @declared_attr
    def plan(self):
        """Parent license plan."""
        return relationship(
            "license_plan",
            back_populates="versions",
            lazy="selectin"
        )

    @declared_attr
    def rules(self):
        """Rules associated with this version."""
        return relationship(
            "license_plan_version_rule",
            back_populates="plan_version",
            lazy="selectin"
        )

    @declared_attr
    def prices(self):
        """Prices associated with this version, one per (period, currency)."""
        return relationship(
            "license_plan_version_price",
            back_populates="plan_version",
            lazy="selectin"
        )

    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_license_plan_version"),
    )

    @property
    def is_free(self) -> bool:
        """Returns True if this version has no billable price."""
        return not any(price.amount > 0 for price in self.prices)

    def price_for(
        self,
        period_id: str,
        currency_id: str = DEFAULT_CURRENCY
    ) -> "Optional[LicensePlanVersionPrice]":
        """
        Get the price of this version for a periodicity and currency.

        Args:
            period_id: Price period ID (e.g., "MONTHLY")
            currency_id: Currency ID (e.g., "EUR")

        Returns:
            The matching LicensePlanVersionPrice, or None if the version is not
            priced for this combination
        """
        for price in self.prices:
            if price.period_id == period_id and price.currency_id == currency_id:
                return price
        return None

    def accessing_users(self) -> list[str]:
        """Users who can access this plan version."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this plan version."""
        return {}


@register_entity()
class LicensePlanVersionPrice(Entity):
    """
    Price of a plan version for a given periodicity and currency.

    Prices are immutable once created: a price change requires a new plan
    version, so that existing subscribers keep the terms they subscribed to
    (grandfathering). The immutability is enforced by
    LicensePlanVersionPriceService.

    Attributes:
        plan_version_id: Reference to the priced plan version
        period_id: Reference to the billing periodicity
        currency_id: Reference to the currency
        amount: Price in currency minor units for one billing period
                (e.g., 4900 = 49.00 EUR)
    """
    __tablename__ = "license_plan_version_price"

    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("license_plan_version.id", ondelete="CASCADE"),
        index=True
    )
    period_id: Mapped[str] = mapped_column(
        ForeignKey("license_price_period.id", ondelete="RESTRICT"),
        index=True
    )
    currency_id: Mapped[str] = mapped_column(
        ForeignKey("license_currency.id", ondelete="RESTRICT"),
        default=DEFAULT_CURRENCY,
        index=True
    )
    amount: Mapped[int] = mapped_column(
        nullable=False,
        comment="Price in currency minor units for one billing period"
    )

    @declared_attr
    def plan_version(self):
        """Priced plan version."""
        return relationship(
            "license_plan_version",
            back_populates="prices",
            lazy="selectin"
        )

    @declared_attr
    def period(self):
        """Billing periodicity."""
        return relationship("license_price_period", lazy="selectin")

    @declared_attr
    def currency(self):
        """Currency this price is expressed in."""
        return relationship("license_currency", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "plan_version_id", "period_id", "currency_id",
            name="uq_license_plan_version_price"
        ),
    )

    @property
    def major_unit_value(self) -> str:
        """
        Amount in major units, as the decimal string payment providers expect
        (e.g., '49.00' for EUR, '4900' for JPY).
        """
        minor_unit = self.currency.minor_unit
        return f"{self.currency.to_major_unit(self.amount):.{minor_unit}f}"

    @property
    def formatted(self) -> str:
        """Human-readable amount (e.g., '49.00 EUR')."""
        return f"{self.major_unit_value} {self.currency_id}"

    def accessing_users(self) -> list[str]:
        """Users who can access this price."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this price."""
        return {}


@register_entity()
class LicensePlanVersionRule(Entity):
    """
    Association between a plan version and a rule with its limit value.

    Attributes:
        plan_version_id: Reference to the plan version
        rule_id: Reference to the rule definition
        limit_value: The limit for this rule in this version
                     - NULL for feature toggles (presence = enabled)
                     - Integer for quotas (e.g., 50 for MAX_USERS)
                     - NULL with quota rule = unlimited
    """
    __tablename__ = "license_plan_version_rule"

    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("license_plan_version.id", ondelete="CASCADE"),
        index=True
    )
    rule_id: Mapped[str] = mapped_column(
        ForeignKey("license_rule.id", ondelete="CASCADE"),
        index=True
    )
    limit_value: Mapped[int | None] = mapped_column(nullable=True)

    @declared_attr
    def plan_version(self):
        """Parent plan version."""
        return relationship(
            "license_plan_version",
            back_populates="rules",
            lazy="selectin"
        )

    @declared_attr
    def rule(self):
        """Rule definition."""
        return relationship("license_rule", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("plan_version_id", "rule_id", name="uq_license_plan_version_rule"),
    )

    def accessing_users(self) -> list[str]:
        """Users who can access this plan version rule."""
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        """Organizations that can access this plan version rule."""
        return {}
