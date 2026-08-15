"""
License plan services.

This module provides:
- LicenseCurrencyService: reference data for pricing currencies
- LicensePricePeriodService: reference data for billing periodicities
- LicensePlanService: CRUD operations for license plans
- LicensePlanVersionService: CRUD operations for plan versions
- LicensePlanVersionPriceService: read and creation of immutable version prices
- LicensePlanVersionRuleService: CRUD operations for version-rule associations
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import DEFAULT_CURRENCY, NO_COMMITMENT
from lys.apps.licensing.errors import (
    DUPLICATE_PRICE,
    DUPLICATE_RULE,
    INVALID_RULE_LIMIT,
    NO_RULE_ON_VERSION,
    INVALID_COMMITMENT_DURATION,
    INVALID_PRICE_AMOUNT,
    UNKNOWN_COMMITMENT,
    UNKNOWN_CURRENCY,
    PLAN_VERSION_NOT_FOUND,
    UNKNOWN_PRICE_PERIOD,
    UNKNOWN_RULE,
)
from lys.apps.licensing.modules.plan.entities import (
    LicenseCommitment,
    LicenseCurrency,
    LicensePlan,
    LicensePlanVersion,
    LicensePlanVersionPrice,
    LicensePlanVersionRule,
    LicensePricePeriod,
)
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class LicenseCurrencyService(EntityService[LicenseCurrency]):
    """
    Service for managing pricing currencies.

    Currencies are reference data: they are provisioned by fixtures and
    referenced by plan version prices.
    """


@register_service()
class LicensePricePeriodService(EntityService[LicensePricePeriod]):
    """
    Service for managing billing periodicities.

    Periodicities are reference data: they are provisioned by fixtures and
    referenced by plan version prices and subscriptions.
    """


@register_service()
class LicenseCommitmentService(EntityService[LicenseCommitment]):
    """
    Service for managing contractual commitments.

    Commitments are reference data: they are provisioned by fixtures and
    referenced by plan version prices.
    """


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
    async def _validate_prices(
        cls,
        prices: List[Dict[str, Any]],
        session: AsyncSession
    ) -> None:
        """
        Validate the price definitions of a version before creating it.

        Args:
            prices: List of {"period_id": str, "amount": int, "currency_id": str,
                    "commitment_id": str}
            session: Database session

        Raises:
            LysError: DUPLICATE_PRICE if two entries share the same terms
            LysError: INVALID_PRICE_AMOUNT if an amount is not strictly positive
            LysError: UNKNOWN_PRICE_PERIOD if a periodicity does not exist or is disabled
            LysError: UNKNOWN_CURRENCY if a currency does not exist or is disabled
            LysError: UNKNOWN_COMMITMENT if a commitment does not exist or is disabled
            LysError: INVALID_COMMITMENT_DURATION if the commitment does not span
                a whole number of billing periods
        """
        period_service = cls.app_manager.get_service("license_price_period")
        currency_service = cls.app_manager.get_service("license_currency")
        commitment_service = cls.app_manager.get_service("license_commitment")

        seen = set()
        for price in prices:
            period_id = price["period_id"]
            currency_id = price.get("currency_id", DEFAULT_CURRENCY)
            commitment_id = price.get("commitment_id", NO_COMMITMENT)
            amount = price["amount"]
            terms = f"{period_id}/{currency_id}/{commitment_id}"

            key = (period_id, currency_id, commitment_id)
            if key in seen:
                raise LysError(
                    DUPLICATE_PRICE,
                    f"Version priced twice for {terms}"
                )
            seen.add(key)

            if not isinstance(amount, int) or amount <= 0:
                raise LysError(
                    INVALID_PRICE_AMOUNT,
                    f"Price for {terms} must be a positive integer, got {amount!r}"
                )

            period = await period_service.get_by_id(period_id, session)
            if period is None or not period.enabled:
                raise LysError(
                    UNKNOWN_PRICE_PERIOD,
                    f"Price period {period_id} does not exist or is disabled"
                )

            currency = await currency_service.get_by_id(currency_id, session)
            if currency is None or not currency.enabled:
                raise LysError(
                    UNKNOWN_CURRENCY,
                    f"Currency {currency_id} does not exist or is disabled"
                )

            commitment = await commitment_service.get_by_id(commitment_id, session)
            if commitment is None or not commitment.enabled:
                raise LysError(
                    UNKNOWN_COMMITMENT,
                    f"Commitment {commitment_id} does not exist or is disabled"
                )

            # A commitment ending mid-period would leave a partially billed
            # period nobody can settle, so it must span whole billing periods
            if commitment.duration_months % period.interval_months != 0:
                raise LysError(
                    INVALID_COMMITMENT_DURATION,
                    f"Commitment {commitment_id} lasts {commitment.duration_months} months, "
                    f"which is not a whole number of {period.interval_months} month periods"
                )

    @classmethod
    async def _validate_rules(
        cls,
        rules: List[Dict[str, Any]],
        session: AsyncSession
    ) -> None:
        """
        Validate the rule definitions of a version before creating it.

        Args:
            rules: List of {"rule_id": str, "limit_value": int | None}
            session: Database session

        Raises:
            LysError: NO_RULE_ON_VERSION if the version grants nothing
            LysError: DUPLICATE_RULE if the same rule is listed twice
            LysError: UNKNOWN_RULE if a rule does not exist or is disabled
            LysError: INVALID_RULE_LIMIT if a limit is negative
        """
        version_rule_service = cls.app_manager.get_service("license_plan_version_rule")

        # A quota rule missing from a version is read as unlimited by the
        # checker, so a version granting nothing explicitly grants everything.
        # Unlimited has its own representation, a null limit, and expressing it
        # must stay deliberate.
        if not rules:
            raise LysError(
                NO_RULE_ON_VERSION,
                "A plan version must declare at least one rule: an undeclared quota "
                "is treated as unlimited. Use a null limit to grant unlimited."
            )

        seen = set()
        for rule in rules:
            rule_id = rule["rule_id"]
            limit_value = rule.get("limit_value")

            if rule_id in seen:
                raise LysError(
                    DUPLICATE_RULE,
                    f"Rule {rule_id} listed twice on the same version"
                )
            seen.add(rule_id)

            await version_rule_service.validate_rule(rule_id, limit_value, session)

    @classmethod
    async def create_new_version(
        cls,
        plan_id: str,
        session: AsyncSession,
        prices: Optional[List[Dict[str, Any]]] = None,
        rules: Optional[List[Dict[str, Any]]] = None
    ) -> LicensePlanVersion:
        """
        Create a new version for a plan, with its prices and its rules.

        Automatically increments the version number and disables the previous
        version. Prices and rules are created together with the version, in the
        same transaction: the new version becomes the offered one as soon as it
        exists, so a version published without its rules would grant nothing to
        the clients landing on it, and prices cannot be added afterwards without
        publishing yet another version.

        An empty price list produces a free version, but the rule list is never
        empty: see _validate_rules.

        Args:
            plan_id: License plan ID
            session: Database session
            prices: List of {"period_id": str, "amount": int, "currency_id": str,
                    "commitment_id": str}, amount in currency minor units.
                    currency_id defaults to DEFAULT_CURRENCY and commitment_id
                    to NO_COMMITMENT
            rules: List of {"rule_id": str, "limit_value": int | None}, at least
                   one. A null limit means unlimited for a quota, or grants a
                   feature toggle

        Returns:
            New LicensePlanVersion entity

        Raises:
            LysError: if a price definition is invalid, see _validate_prices
            LysError: if a rule definition is invalid, see _validate_rules
        """
        prices = prices or []
        rules = rules or []
        await cls._validate_prices(prices, session)
        await cls._validate_rules(rules, session)

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
            enabled=True
        )

        # Create its prices
        price_service = cls.app_manager.get_service("license_plan_version_price")
        for price in prices:
            await price_service.create(
                session,
                plan_version_id=new_version.id,
                period_id=price["period_id"],
                currency_id=price.get("currency_id", DEFAULT_CURRENCY),
                commitment_id=price.get("commitment_id", NO_COMMITMENT),
                amount=price["amount"]
            )

        # Create its rules
        rule_service = cls.app_manager.get_service("license_plan_version_rule")
        for rule in rules:
            await rule_service.set_rule_limit(
                plan_version_id=new_version.id,
                rule_id=rule["rule_id"],
                limit_value=rule.get("limit_value"),
                session=session
            )

        return new_version


    @classmethod
    async def set_enabled(
        cls,
        plan_version_id: str,
        enabled: bool,
        session: AsyncSession
    ) -> LicensePlanVersion:
        """
        Enable or disable a plan version.

        Only one version of a plan can be enabled at a time, so enabling one
        disables the others. Disabling withdraws the version from the catalogue
        without touching the subscriptions that reference it: they keep the
        rules and the price they were sold.

        Args:
            plan_version_id: Plan version ID
            enabled: Whether the version can be selected for new subscriptions
            session: Database session

        Returns:
            The updated LicensePlanVersion

        Raises:
            LysError: PLAN_VERSION_NOT_FOUND if the version does not exist
        """
        version = await cls.get_by_id(plan_version_id, session)
        if version is None:
            raise LysError(
                PLAN_VERSION_NOT_FOUND,
                f"Plan version {plan_version_id} not found"
            )

        if enabled:
            stmt = select(cls.entity_class).where(
                cls.entity_class.plan_id == version.plan_id,
                cls.entity_class.enabled == True,
                cls.entity_class.id != version.id
            )
            result = await session.execute(stmt)
            for other in result.scalars():
                other.enabled = False

        version.enabled = enabled
        return version


@register_service()
class LicensePlanVersionPriceService(EntityService[LicensePlanVersionPrice]):
    """
    Service for managing plan version prices.

    Prices are created by LicensePlanVersionService.create_new_version and are
    not meant to be modified afterwards: changing what a version costs would
    change it for every existing subscriber. A price change is published as a
    new plan version, which is what preserves grandfathering.

    Any edition webservice built on this entity must therefore expose neither
    amount, period_id nor currency_id.
    """


@register_service()
class LicensePlanVersionRuleService(EntityService[LicensePlanVersionRule]):
    """
    Service for managing version-rule associations.

    Associates rules with plan versions and defines limit values for quotas.
    """

    @classmethod
    async def get_rules_for_version(
        cls,
        plan_version_id: str,
        session: AsyncSession
    ) -> List[LicensePlanVersionRule]:
        """
        Get all rules associated with a plan version.

        Args:
            plan_version_id: Plan version ID
            session: Database session

        Returns:
            List of LicensePlanVersionRule entities
        """
        stmt = select(cls.entity_class).where(
            cls.entity_class.plan_version_id == plan_version_id
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def validate_rule(
        cls,
        rule_id: str,
        limit_value: int | None,
        session: AsyncSession
    ) -> None:
        """
        Validate a rule and its limit before associating them with a version.

        Args:
            rule_id: Rule ID
            limit_value: Limit value (None for feature toggles or unlimited)
            session: Database session

        Raises:
            LysError: UNKNOWN_RULE if the rule does not exist or is disabled
            LysError: INVALID_RULE_LIMIT if the limit is negative
        """
        if limit_value is not None and (not isinstance(limit_value, int) or limit_value < 0):
            raise LysError(
                INVALID_RULE_LIMIT,
                f"Limit of rule {rule_id} must be a positive integer or null, "
                f"got {limit_value!r}"
            )

        rule_service = cls.app_manager.get_service("license_rule")
        rule_definition = await rule_service.get_by_id(rule_id, session)

        if rule_definition is None or not rule_definition.enabled:
            raise LysError(
                UNKNOWN_RULE,
                f"Rule {rule_id} does not exist or is disabled"
            )

    @classmethod
    async def set_rule_limit(
        cls,
        plan_version_id: str,
        rule_id: str,
        limit_value: int | None,
        session: AsyncSession
    ) -> LicensePlanVersionRule:
        """
        Set or update a rule limit for a plan version.

        Unlike prices, which are immutable once published, a rule can be changed
        on a version that has already been sold, and the change applies at once
        to every subscriber of that version: the checker reads the current limit,
        not the one in force on the subscription date.

        The framework does not arbitrate this. Lowering what a client already
        paid for is a unilateral change of terms, which business practice only
        allows at renewal, through a new version; raising a limit, or correcting
        a version nobody has subscribed to yet, is harmless. Applications
        enforcing such a policy must implement it themselves.

        Args:
            plan_version_id: Plan version ID
            rule_id: Rule ID
            limit_value: Limit value (None for feature toggles or unlimited)
            session: Database session

        Returns:
            LicensePlanVersionRule entity (created or updated)

        Raises:
            LysError: PLAN_VERSION_NOT_FOUND if the version does not exist
            LysError: UNKNOWN_RULE if the rule does not exist or is disabled
            LysError: INVALID_RULE_LIMIT if the limit is negative
        """
        version_service = cls.app_manager.get_service("license_plan_version")
        if await version_service.get_by_id(plan_version_id, session) is None:
            raise LysError(
                PLAN_VERSION_NOT_FOUND,
                f"Plan version {plan_version_id} not found"
            )

        await cls.validate_rule(rule_id, limit_value, session)

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