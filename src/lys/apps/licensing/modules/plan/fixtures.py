"""
Fixtures for license plans and plan versions.

This module provides:
- LicensePlanDevFixtures: Default plans (FREE, STARTER, PRO)
- LicensePlanVersionDevFixtures: Plan versions with pricing and rule associations

After loading plan versions, automatically syncs paid plans to payment provider if configured.
"""
import logging

from typing import Any, Dict, List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import (
    DEFAULT_APPLICATION,
    FREE_PLAN,
    STARTER_PLAN,
    PRO_PLAN,
    MAX_USERS,
    MAX_PROJECTS_PER_MONTH,
)
from lys.apps.licensing.modules.mollie.services import is_payment_configured
from lys.apps.licensing.modules.plan.services import (
    LicensePlanService,
    LicensePlanVersionService,
)
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import EntityFixturesModel, ParametricEntityFixturesModel
from lys.core.registries import register_fixture

logger = logging.getLogger(__name__)


@register_fixture(depends_on=["LicenseApplicationDevFixtures", "LicenseRuleFixtures"])
class LicensePlanDevFixtures(EntityFixtures[LicensePlanService]):
    """
    Fixtures for license plan types.

    Plans represent subscription tiers available to clients.
    """
    model = ParametricEntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV, ]

    data_list = [
        {
            "id": FREE_PLAN,
            "attributes": {
                "app_id": DEFAULT_APPLICATION,
                "enabled": True,
                "description": "Free plan with basic features and limited quotas"
            }
        },
        {
            "id": STARTER_PLAN,
            "attributes": {
                "app_id": DEFAULT_APPLICATION,
                "enabled": True,
                "description": "Starter plan for small teams"
            }
        },
        {
            "id": PRO_PLAN,
            "attributes": {
                "app_id": DEFAULT_APPLICATION,
                "enabled": True,
                "description": "Professional plan for growing businesses"
            }
        },
    ]


class LicensePlanVersionFixturesModel(EntityFixturesModel):
    """Model for plan version fixtures with rules."""

    class AttributesModel(EntityFixturesModel.AttributesModel):
        plan_id: str
        version: int
        price_monthly: int | None = None
        price_yearly: int | None = None
        currency: str = "eur"
        enabled: bool = True
        rules: List[Dict[str, Any]] = []

    attributes: AttributesModel


@register_fixture(depends_on=["LicensePlanDevFixtures"])
class LicensePlanVersionDevFixtures(EntityFixtures[LicensePlanVersionService]):
    """
    Fixtures for license plan versions with pricing and rules.

    Each version defines:
    - Pricing (monthly/yearly in cents, None = free)
    - Rules with limit values (quotas and feature toggles)

    Note: provider_product_id is NOT set here - it will be auto-filled
    by the payment provider sync service if configured.
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
                "price_monthly": None,
                "price_yearly": None,
                "currency": "eur",
                "enabled": True,
                "rules": [
                    {"rule_id": MAX_USERS, "limit_value": 5},
                    {"rule_id": MAX_PROJECTS_PER_MONTH, "limit_value": 3},
                ]
            }
        },
        # STARTER v1: 19€/month or 190€/year
        {
            "attributes": {
                "plan_id": STARTER_PLAN,
                "version": 1,
                "price_monthly": 1900,
                "price_yearly": 19000,
                "currency": "eur",
                "enabled": True,
                "rules": [
                    {"rule_id": MAX_USERS, "limit_value": 25},
                    {"rule_id": MAX_PROJECTS_PER_MONTH, "limit_value": 20},
                ]
            }
        },
        # PRO v1: 49€/month or 490€/year
        {
            "attributes": {
                "plan_id": PRO_PLAN,
                "version": 1,
                "price_monthly": 4900,
                "price_yearly": 49000,
                "currency": "eur",
                "enabled": True,
                "rules": [
                    {"rule_id": MAX_USERS, "limit_value": 100},
                    {"rule_id": MAX_PROJECTS_PER_MONTH, "limit_value": None},  # Unlimited
                ]
            }
        },
    ]

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

        For existing entities (upsert), looks up existing rules and updates them.

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

            # Create new rule
            version_rule = version_rule_class(
                rule_id=rule_id,
                limit_value=limit_value
            )
            version_rules.append(version_rule)

        return version_rules

    @classmethod
    async def load(cls):
        """
        Load fixtures and sync to payment provider.

        Overrides parent to add payment provider synchronization after fixture loading.
        """
        await super().load()
        await cls._sync_to_payment_provider()

    @classmethod
    async def _sync_to_payment_provider(cls) -> None:
        """
        Synchronize paid plan versions to payment provider.

        Only runs if payment provider is configured. Validates plan versions
        for the configured payment provider (Mollie, etc.).
        """
        if not is_payment_configured():
            logger.debug("Payment provider not configured, skipping sync")
            return

        try:
            mollie_sync_service = cls.app_manager.get_service("mollie_sync")
        except KeyError:
            logger.debug("MollieSyncService not registered, skipping sync")
            return

        db_manager = cls.app_manager.database
        async with db_manager.get_session() as session:
            validated = await mollie_sync_service.sync_all_enabled_versions(session)
            if validated:
                logger.info(f"Validated {len(validated)} plan versions for payment provider")