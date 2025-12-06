"""
License plan entity definitions.

This module defines:
- LicensePlan: Plan types (FREE, STARTER, PRO, ENTERPRISE)
- LicensePlanVersion: Versioned plans with pricing for grandfathering
- LicensePlanVersionRule: Association between a version and a rule with its limit value
"""

from typing import TYPE_CHECKING, Dict, List, Self

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class LicensePlan(ParametricEntity):
    """
    License plan type.

    Attributes:
        id: Plan identifier (e.g., "FREE", "STARTER", "PRO", "ENTERPRISE")
        client_id: If set, this is a custom plan for a specific client
        description: Human-readable description
        enabled: If False, plan cannot be selected for new subscriptions
                 (existing subscriptions remain active)
    """
    __tablename__ = "license_plan"

    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

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
class LicensePlanVersion(Entity):
    """
    Version of a license plan.

    Each plan can have multiple versions to support grandfathering:
    existing subscribers keep their version's rules even if the plan changes.

    Attributes:
        plan_id: Reference to the parent plan
        version: Version number (1, 2, 3...)
        stripe_product_id: Stripe Product ID (auto-filled by StripeSyncService)
        price_monthly: Monthly price in cents (e.g., 4900 = 49€). NULL = free
        price_yearly: Yearly price in cents (e.g., 49000 = 490€). NULL = free
        currency: Currency code (default: "eur")
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

    # Stripe sync - stripe_product_id is auto-filled by StripeSyncService
    stripe_product_id: Mapped[str | None] = mapped_column(nullable=True)

    # Pricing (in cents) - used to create Stripe Prices
    price_monthly: Mapped[int | None] = mapped_column(nullable=True)
    price_yearly: Mapped[int | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(default="eur")

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

    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_license_plan_version"),
    )

    @property
    def is_free(self) -> bool:
        """Returns True if this is a free plan (no prices defined)."""
        return self.price_monthly is None and self.price_yearly is None

    def accessing_users(self) -> List:
        """Users who can access this plan version."""
        return []

    def accessing_organizations(self) -> Dict[str, List[Self]]:
        """Organizations that can access this plan version."""
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

    def accessing_users(self) -> List:
        """Users who can access this plan version rule."""
        return []

    def accessing_organizations(self) -> Dict[str, List[Self]]:
        """Organizations that can access this plan version rule."""
        return {}