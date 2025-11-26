"""
Core licensing services.

This module provides:
- LicenseCheckerService: Rule validation and enforcement
"""
import logging
from typing import Dict, Any, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.errors import (
    NO_ACTIVE_SUBSCRIPTION,
    QUOTA_EXCEEDED,
    FEATURE_NOT_AVAILABLE,
    UNKNOWN_RULE,
    DOWNGRADE_RULE_NOT_FOUND
)
from lys.core.errors import LysError
from lys.core.services import Service
from lys.core.registries import register_service

logger = logging.getLogger(__name__)


@register_service()
class LicenseCheckerService(Service):
    """
    Service for checking and enforcing license rules.

    Uses the validators and downgraders registries to execute
    rule-specific validation and downgrade logic.
    """

    service_name = "license_checker"

    @classmethod
    async def check_quota(
        cls,
        client_id: str,
        rule_id: str,
        session: AsyncSession
    ) -> Tuple[bool, int, int]:
        """
        Check if a quota rule is satisfied for a client.

        Args:
            client_id: Client ID
            rule_id: Rule ID (e.g., "MAX_USERS")
            session: Database session

        Returns:
            Tuple of (is_valid, current_count, limit)

        Raises:
            LysError: If client has no subscription or rule is unknown
        """
        # Get client's subscription
        subscription_service = cls.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(client_id, session)

        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Get rule limit from subscription's plan version
        version_rule_service = cls.app_manager.get_service("version_rule")
        version_rules = await version_rule_service.get_rules_for_version(
            subscription.plan_version_id, session
        )

        # Find the specific rule
        rule_config = None
        for vr in version_rules:
            if vr.rule_id == rule_id:
                rule_config = vr
                break

        if not rule_config:
            # Rule not configured for this plan = unlimited or not applicable
            return (True, 0, -1)

        limit_value = rule_config.limit_value

        # Get validator from registry
        validators_registry = cls.app_manager.registry.get_registry("validators")
        if not validators_registry:
            logger.warning("Validators registry not found")
            return (True, 0, limit_value or -1)

        validator = validators_registry.get(rule_id)
        if not validator:
            logger.warning(f"No validator found for rule {rule_id}")
            # No validator = assume valid
            return (True, 0, limit_value or -1)

        # Execute validator
        return await validator(session, client_id, limit_value)

    @classmethod
    async def enforce_quota(
        cls,
        client_id: str,
        rule_id: str,
        session: AsyncSession
    ) -> None:
        """
        Enforce a quota rule - raises error if quota exceeded.

        Args:
            client_id: Client ID
            rule_id: Rule ID
            session: Database session

        Raises:
            LysError: If quota is exceeded
        """
        is_valid, current, limit = await cls.check_quota(client_id, rule_id, session)

        if not is_valid:
            raise LysError(
                QUOTA_EXCEEDED,
                f"Quota exceeded for {rule_id}: {current}/{limit}"
            )

    @classmethod
    async def check_feature(
        cls,
        client_id: str,
        rule_id: str,
        session: AsyncSession
    ) -> bool:
        """
        Check if a feature is available for a client.

        Feature toggles are binary: the rule is either present in the
        plan version (enabled) or not (disabled).

        Args:
            client_id: Client ID
            rule_id: Feature rule ID (e.g., "EXPORT_PDF_ACCESS")
            session: Database session

        Returns:
            True if feature is available

        Raises:
            LysError: If client has no subscription
        """
        # Get client's subscription
        subscription_service = cls.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(client_id, session)

        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Get rules from subscription's plan version
        version_rule_service = cls.app_manager.get_service("version_rule")
        version_rules = await version_rule_service.get_rules_for_version(
            subscription.plan_version_id, session
        )

        # Feature is enabled if rule is present in plan version
        for vr in version_rules:
            if vr.rule_id == rule_id:
                return True

        return False

    @classmethod
    async def enforce_feature(
        cls,
        client_id: str,
        rule_id: str,
        session: AsyncSession
    ) -> None:
        """
        Enforce a feature rule - raises error if feature not available.

        Args:
            client_id: Client ID
            rule_id: Feature rule ID
            session: Database session

        Raises:
            LysError: If feature is not available
        """
        has_feature = await cls.check_feature(client_id, rule_id, session)

        if not has_feature:
            raise LysError(
                FEATURE_NOT_AVAILABLE,
                f"Feature {rule_id} is not available in your plan"
            )

    @classmethod
    async def get_client_limits(
        cls,
        client_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Get all rule limits for a client's subscription.

        Args:
            client_id: Client ID
            session: Database session

        Returns:
            Dict mapping rule_id to limit info:
            {
                "MAX_USERS": {"limit": 50, "type": "quota"},
                "EXPORT_PDF_ACCESS": {"enabled": True, "type": "feature"},
                ...
            }

        Raises:
            LysError: If client has no subscription
        """
        # Get client's subscription
        subscription_service = cls.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(client_id, session)

        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Get rules from subscription's plan version
        version_rule_service = cls.app_manager.get_service("version_rule")
        version_rules = await version_rule_service.get_rules_for_version(
            subscription.plan_version_id, session
        )

        limits = {}
        for vr in version_rules:
            if vr.limit_value is not None:
                # Quota rule
                limits[vr.rule_id] = {
                    "limit": vr.limit_value,
                    "type": "quota"
                }
            else:
                # Feature toggle
                limits[vr.rule_id] = {
                    "enabled": True,
                    "type": "feature"
                }

        return limits

    @classmethod
    async def validate_downgrade(
        cls,
        client_id: str,
        new_plan_version_id: str,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Validate if a client can downgrade to a new plan.

        Checks all rules and returns violations that would occur.

        Args:
            client_id: Client ID
            new_plan_version_id: Target plan version ID
            session: Database session

        Returns:
            List of violations:
            [
                {"rule_id": "MAX_USERS", "current": 75, "new_limit": 50},
                ...
            ]
        """
        violations = []

        # Get current subscription
        subscription_service = cls.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(client_id, session)

        if not subscription:
            return violations

        # Get new plan version rules
        version_rule_service = cls.app_manager.get_service("version_rule")
        new_rules = await version_rule_service.get_rules_for_version(
            new_plan_version_id, session
        )

        # Get validators registry
        validators_registry = cls.app_manager.registry.get_registry("validators")

        for new_rule in new_rules:
            if new_rule.limit_value is None:
                continue  # Skip feature toggles

            # Check current usage against new limit
            if validators_registry:
                validator = validators_registry.get(new_rule.rule_id)
                if validator:
                    is_valid, current, _ = await validator(
                        session, client_id, new_rule.limit_value
                    )
                    if not is_valid:
                        violations.append({
                            "rule_id": new_rule.rule_id,
                            "current": current,
                            "new_limit": new_rule.limit_value
                        })

        return violations

    @classmethod
    async def execute_downgrade(
        cls,
        client_id: str,
        new_plan_version_id: str,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Execute downgrade actions for all violated rules.

        Calls the downgrader for each rule that exceeds the new plan's limits.

        Args:
            client_id: Client ID
            new_plan_version_id: Target plan version ID
            session: Database session

        Returns:
            List of downgrade results
        """
        results = []

        # Get violations
        violations = await cls.validate_downgrade(client_id, new_plan_version_id, session)

        # Get downgraders registry
        downgraders_registry = cls.app_manager.registry.get_registry("downgraders")

        for violation in violations:
            rule_id = violation["rule_id"]
            new_limit = violation["new_limit"]

            if downgraders_registry:
                downgrader = downgraders_registry.get(rule_id)
                if downgrader:
                    success = await downgrader(session, client_id, new_limit)
                    results.append({
                        "rule_id": rule_id,
                        "success": success,
                        "new_limit": new_limit
                    })
                else:
                    logger.warning(f"No downgrader found for rule {rule_id}")
                    results.append({
                        "rule_id": rule_id,
                        "success": False,
                        "error": "No downgrader found"
                    })

        return results