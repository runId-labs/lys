"""
Fixtures for license plans and plan versions.

This module provides:
- LicenseCurrencyFixtures: Currencies available for pricing
- LicenseCommitmentFixtures: Contractual commitments
- LicensePricePeriodFixtures: Billing periodicities
- LicensePlanDevFixtures: Default plans (FREE, STARTER, PRO)
- LicensePlanVersionDevFixtures: Plan versions with pricing and rule associations
"""
import logging

from typing import Any, Dict, List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import (
    DEFAULT_APPLICATION,
    DEFAULT_CURRENCY,
    EUR_CURRENCY,
    FREE_PLAN,
    MAX_USERS,
    MONTHLY_PERIOD,
    NO_COMMITMENT,
    YEARLY_PERIOD,
)
from lys.apps.licensing.modules.plan.models import (
    LicenseCommitmentFixturesModel,
    LicenseCurrencyFixturesModel,
    LicensePlanVersionFixturesModel,
    LicensePricePeriodFixturesModel,
)
from lys.apps.licensing.modules.plan.services import (
    LicenseCommitmentService,
    LicenseCurrencyService,
    LicensePlanService,
    LicensePlanVersionService,
    LicensePricePeriodService,
)
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture

logger = logging.getLogger(__name__)


@register_fixture()
class LicenseCurrencyFixtures(EntityFixtures[LicenseCurrencyService]):
    """
    Fixtures for pricing currencies.

    Reference data loaded in every environment. Business applications selling
    in other currencies register their own fixture listing the full set.
    """
    model = LicenseCurrencyFixturesModel

    data_list = [
        {
            "id": EUR_CURRENCY,
            "attributes": {
                "enabled": True,
                "minor_unit": 2,
                "description": "Euro"
            }
        },
    ]


@register_fixture()
class LicensePricePeriodFixtures(EntityFixtures[LicensePricePeriodService]):
    """
    Fixtures for billing periodicities.

    Reference data loaded in every environment. Additional cadences (quarterly,
    half-yearly...) only require a new entry with its interval in months.
    """
    model = LicensePricePeriodFixturesModel

    data_list = [
        {
            "id": MONTHLY_PERIOD,
            "attributes": {
                "enabled": True,
                "interval_months": 1,
                "description": "Monthly billing"
            }
        },
        {
            "id": YEARLY_PERIOD,
            "attributes": {
                "enabled": True,
                "interval_months": 12,
                "description": "Yearly billing"
            }
        },
    ]


@register_fixture(depends_on=["LicenseApplicationDevFixtures", "LicenseRuleFixtures"])
class LicensePlanDevFixtures(EntityFixtures[LicensePlanService]):
    """
    Fixtures for license plan types.

    Only the free plan is shipped, because the framework depends on it: a new
    client is automatically subscribed to it, and a cancellation falls back to
    it. Commercial tiers belong to each application's own offer.

    Plans not listed here are left untouched, so that custom plans negotiated
    with a single client and created at runtime are not disabled on the next
    fixture run. Retiring a plan is therefore an explicit `enabled: False`.
    """
    model = ParametricEntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV, ]
    delete_previous_data = False

    data_list = [
        {
            "id": FREE_PLAN,
            "attributes": {
                "app_id": DEFAULT_APPLICATION,
                "enabled": True,
                "description": "Free plan with basic features and limited quotas"
            }
        },
    ]


@register_fixture()
class LicenseCommitmentFixtures(EntityFixtures[LicenseCommitmentService]):
    """
    Fixtures for contractual commitments.

    Reference data loaded in every environment. Only the absence of commitment
    is shipped: binding tiers belong to each application's commercial offer, and
    are added by registering a fixture listing the full set.
    """
    model = LicenseCommitmentFixturesModel

    data_list = [
        {
            "id": NO_COMMITMENT,
            "attributes": {
                "enabled": True,
                "duration_months": 0,
                "renewal_months": 0,
                "notice_months": 0,
                "description": "No commitment"
            }
        },
    ]


@register_fixture(depends_on=[
    "LicensePlanDevFixtures",
    "LicenseCurrencyFixtures",
    "LicensePricePeriodFixtures",
    "LicenseCommitmentFixtures",
])
class LicensePlanVersionDevFixtures(EntityFixtures[LicensePlanVersionService]):
    """
    Fixture for the free plan version.

    Only the free plan is versioned here, since it is the only plan the
    framework ships. Priced versions belong to each application's own offer and
    are published through the plan version webservices.

    A version defines:
    - Prices, one per (period, currency, commitment), in currency minor units.
      No price entry means the version is free.
    - Rules with limit values (quotas and feature toggles)

    Prices are immutable once created: changing a price in this fixture has no
    effect on an already loaded version. Publish a new version entry instead,
    so that existing subscribers keep the terms they subscribed to.
    """
    model = LicensePlanVersionFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV, ]
    delete_previous_data=False

    data_list = [
        # FREE v1: Basic features with strict limits
        {
            "attributes": {
                "plan_id": FREE_PLAN,
                "version": 1,
                "enabled": True,
                "prices": [],
                "rules": [
                    {"rule_id": MAX_USERS, "limit_value": 5},
                ]
            }
        },
    ]

    @classmethod
    async def format_prices(
        cls,
        prices_data: List[Dict[str, Any]],
        session: AsyncSession,
        extra_data: Dict[str, Any] | None = None
    ) -> List:
        """
        Convert price definitions to LicensePlanVersionPrice objects.

        For new entities, SQLAlchemy sets plan_version_id automatically when the
        version is added to the session via the relationship.

        For existing entities (upsert), prices already stored are returned
        unchanged: a published price is immutable, so a price change must go
        through a new plan version. A mismatch is logged to make the discarded
        fixture change visible. A price the version does not carry yet is created
        with its parent set explicitly, for the same reason as the rules.

        Args:
            prices_data: List of {"period_id": str, "amount": int,
                         "currency_id": str, "commitment_id": str}
            session: Database session
            extra_data: Optional context with parent_id for upsert

        Returns:
            List of LicensePlanVersionPrice objects
        """
        price_class = cls.app_manager.get_entity("license_plan_version_price")
        parent_id = extra_data.get("parent_id") if extra_data else None

        prices = []
        for price_data in prices_data:
            period_id = price_data["period_id"]
            currency_id = price_data.get("currency_id", DEFAULT_CURRENCY)
            commitment_id = price_data.get("commitment_id", NO_COMMITMENT)
            amount = price_data["amount"]

            if parent_id:
                # Upsert mode: an existing price is never modified
                stmt = select(price_class).where(
                    and_(
                        price_class.plan_version_id == parent_id,
                        price_class.period_id == period_id,
                        price_class.currency_id == currency_id,
                        price_class.commitment_id == commitment_id
                    )
                ).limit(1)
                result = await session.execute(stmt)
                existing_price = result.scalars().one_or_none()

                if existing_price:
                    if existing_price.amount != amount:
                        logger.warning(
                            f"Ignoring price change for plan version {parent_id} "
                            f"({period_id}/{currency_id}/{commitment_id}): "
                            f"stored {existing_price.amount}, "
                            f"fixture {amount}. Publish a new plan version instead."
                        )
                    prices.append(existing_price)
                    continue

            prices.append(price_class(
                period_id=period_id,
                currency_id=currency_id,
                commitment_id=commitment_id,
                amount=amount,
                **({"plan_version_id": parent_id} if parent_id else {})
            ))

        return prices

    @classmethod
    async def format_rules(
        cls,
        rules_data: List[Dict[str, Any]],
        session: AsyncSession,
        extra_data: Dict[str, Any] | None = None
    ) -> List:
        """
        Convert rule definitions to LicensePlanVersionRule objects.

        For new entities, SQLAlchemy will automatically set plan_version_id
        when the version is added to the session via the relationship.

        For existing entities (upsert), looks up existing rules and updates
        them. A rule the version does not carry yet is created with its parent
        set explicitly, and the rules the fixture does not list are kept: an
        application refining a version the framework ships must not see its own
        rules detached on the next boot.

        Args:
            rules_data: List of {"rule_id": str, "limit_value": int|None}
            session: Database session
            extra_data: Optional context with parent_id for upsert

        Returns:
            List of LicensePlanVersionRule objects
        """
        version_rule_class = cls.app_manager.get_entity("license_plan_version_rule")
        parent_id = extra_data.get("parent_id") if extra_data else None

        version_rules = []
        for rule_data in rules_data:
            rule_id = rule_data["rule_id"]
            limit_value = rule_data.get("limit_value")

            if parent_id:
                # Upsert mode: look for existing rule
                stmt = select(version_rule_class).where(
                    and_(
                        version_rule_class.plan_version_id == parent_id,
                        version_rule_class.rule_id == rule_id
                    )
                ).limit(1)
                result = await session.execute(stmt)
                existing_rule = result.scalars().one_or_none()

                if existing_rule:
                    # Update existing rule
                    existing_rule.limit_value = limit_value
                    version_rules.append(existing_rule)
                    continue

            # Create new rule. On an existing version the parent is set here:
            # the update path assigns this list to the version rather than
            # cascading through the relationship, so a rule added to a version
            # already stored would be inserted without its parent.
            version_rule = version_rule_class(
                rule_id=rule_id,
                limit_value=limit_value,
                **({"plan_version_id": parent_id} if parent_id else {})
            )
            version_rules.append(version_rule)

        if parent_id:
            # Keep the rules this fixture does not list. A version can be
            # refined by an application — the framework ships a free plan, an
            # application adds its own quota to it — and both fixtures then
            # describe the same version. Assigning only what is listed would
            # detach the others, which the database refuses since a rule cannot
            # exist without its version. Removing a rule is deliberate enough to
            # go through the webservice.
            listed = {rule["rule_id"] for rule in rules_data}
            stmt = select(version_rule_class).where(
                and_(
                    version_rule_class.plan_version_id == parent_id,
                    version_rule_class.rule_id.notin_(listed)
                )
            )
            result = await session.execute(stmt)
            version_rules.extend(result.scalars().all())

        return version_rules

