"""
License plan services.

This module provides:
- LicensePlanService: CRUD operations for license plans
- LicensePlanVersionService: CRUD operations for plan versions
- VersionRuleService: CRUD operations for version-rule associations
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.modules.plan.entities import LicensePlan, LicensePlanVersion, VersionRule
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class LicensePlanService(EntityService[LicensePlan]):
    """
    Service for managing license plans.

    License plans represent subscription tiers (FREE, STARTER, PRO, ENTERPRISE).
    Plans can be global or custom (client-specific).
    """

    @classmethod
    async def get_available_plans(
        cls,
        session: AsyncSession,
        client_id: str | None = None
    ) -> List[LicensePlan]:
        """
        Get all available plans for subscription.

        Returns global plans plus any custom plans for the specified client.
        Only returns enabled plans.

        Args:
            session: Database session
            client_id: Optional client ID for custom plans

        Returns:
            List of available LicensePlan entities
        """
        stmt = select(cls.entity_class).where(cls.entity_class.enabled == True)

        if client_id:
            # Global plans (client_id is NULL) + custom plans for this client
            stmt = stmt.where(
                (cls.entity_class.client_id == None) |
                (cls.entity_class.client_id == client_id)
            )
        else:
            # Only global plans
            stmt = stmt.where(cls.entity_class.client_id == None)

        result = await session.execute(stmt)
        return list(result.scalars().all())


@register_service()
class LicensePlanVersionService(EntityService[LicensePlanVersion]):
    """
    Service for managing license plan versions.

    Plan versions support grandfathering: existing subscribers keep their
    version's rules even when new versions are created.
    """

    @classmethod
    async def get_current_version(
        cls,
        plan_id: str,
        session: AsyncSession
    ) -> LicensePlanVersion | None:
        """
        Get the current (enabled) version for a plan.

        Args:
            plan_id: License plan ID
            session: Database session

        Returns:
            Current LicensePlanVersion or None
        """
        stmt = select(cls.entity_class).where(
            cls.entity_class.plan_id == plan_id,
            cls.entity_class.enabled == True
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_new_version(
        cls,
        plan_id: str,
        session: AsyncSession,
        price_monthly: int | None = None,
        price_yearly: int | None = None,
        currency: str = "eur"
    ) -> LicensePlanVersion:
        """
        Create a new version for a plan.

        Automatically increments the version number and disables the previous version.

        Args:
            plan_id: License plan ID
            session: Database session
            price_monthly: Monthly price in cents (None = free)
            price_yearly: Yearly price in cents (None = free)
            currency: Currency code (default: "eur")

        Returns:
            New LicensePlanVersion entity
        """
        # Get current max version number
        stmt = select(cls.entity_class.version).where(
            cls.entity_class.plan_id == plan_id
        ).order_by(cls.entity_class.version.desc()).limit(1)
        result = await session.execute(stmt)
        current_version = result.scalar_one_or_none() or 0

        # Disable all existing versions for this plan
        existing_versions_stmt = select(cls.entity_class).where(
            cls.entity_class.plan_id == plan_id,
            cls.entity_class.enabled == True
        )
        existing_result = await session.execute(existing_versions_stmt)
        for version in existing_result.scalars():
            version.enabled = False

        # Create new version
        new_version = await cls.create(
            session,
            plan_id=plan_id,
            version=current_version + 1,
            enabled=True,
            price_monthly=price_monthly,
            price_yearly=price_yearly,
            currency=currency
        )

        return new_version


@register_service()
class VersionRuleService(EntityService[VersionRule]):
    """
    Service for managing version-rule associations.

    Associates rules with plan versions and defines limit values for quotas.
    """

    @classmethod
    async def get_rules_for_version(
        cls,
        plan_version_id: str,
        session: AsyncSession
    ) -> List[VersionRule]:
        """
        Get all rules associated with a plan version.

        Args:
            plan_version_id: Plan version ID
            session: Database session

        Returns:
            List of VersionRule entities
        """
        stmt = select(cls.entity_class).where(
            cls.entity_class.plan_version_id == plan_version_id
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def set_rule_limit(
        cls,
        plan_version_id: str,
        rule_id: str,
        limit_value: int | None,
        session: AsyncSession
    ) -> VersionRule:
        """
        Set or update a rule limit for a plan version.

        Args:
            plan_version_id: Plan version ID
            rule_id: Rule ID
            limit_value: Limit value (None for feature toggles or unlimited)
            session: Database session

        Returns:
            VersionRule entity (created or updated)
        """
        # Check if association already exists
        stmt = select(cls.entity_class).where(
            cls.entity_class.plan_version_id == plan_version_id,
            cls.entity_class.rule_id == rule_id
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.limit_value = limit_value
            return existing

        return await cls.create(
            session,
            plan_version_id=plan_version_id,
            rule_id=rule_id,
            limit_value=limit_value
        )