"""
Core licensing services.

This module provides:
- LicenseCheckerService: Rule validation and enforcement

Supports two modes:
1. Database-based checks: Query subscription from DB (for backend operations)
2. JWT-based checks: Use claims from token (fast, no DB query, for request validation)
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.errors import (
    NO_ACTIVE_SUBSCRIPTION,
    QUOTA_EXCEEDED,
    FEATURE_NOT_AVAILABLE,
    UNKNOWN_RULE,
    DOWNGRADE_RULE_NOT_FOUND,
    SUBSCRIPTION_INACTIVE
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
        version_rule_service = cls.app_manager.get_service("license_plan_version_rule")
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

        # Get app_id from subscription's plan version
        await session.refresh(subscription, ["plan_version"])
        plan_version = subscription.plan_version
        await session.refresh(plan_version, ["plan"])
        app_id = plan_version.plan.app_id

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
        return await validator(session, client_id, app_id, limit_value)

    @classmethod
    async def enforce_quota(
        cls,
        client_id: str,
        rule_id: str,
        session: AsyncSession,
        error: Tuple[int, str] | None = None
    ) -> None:
        """
        Enforce a quota rule - raises error if quota exceeded.

        Args:
            client_id: Client ID
            rule_id: Rule ID
            session: Database session
            error: Optional custom error tuple (status_code, error_code).
                   Defaults to QUOTA_EXCEEDED if not provided.

        Raises:
            LysError: If quota is exceeded
        """
        is_valid, current, limit = await cls.check_quota(client_id, rule_id, session)

        if not is_valid:
            raise LysError(
                error or QUOTA_EXCEEDED,
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
        version_rule_service = cls.app_manager.get_service("license_plan_version_rule")
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
        version_rule_service = cls.app_manager.get_service("license_plan_version_rule")
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

        # Get new plan version and its rules
        version_rule_service = cls.app_manager.get_service("license_plan_version_rule")
        new_rules = await version_rule_service.get_rules_for_version(
            new_plan_version_id, session
        )

        # Get app_id from the new plan version
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        new_plan_version = await session.get(plan_version_entity, new_plan_version_id)
        await session.refresh(new_plan_version, ["plan"])
        app_id = new_plan_version.plan.app_id

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
                        session, client_id, app_id, new_rule.limit_value
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

        # Get app_id from the new plan version
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        new_plan_version = await session.get(plan_version_entity, new_plan_version_id)
        await session.refresh(new_plan_version, ["plan"])
        app_id = new_plan_version.plan.app_id

        # Get downgraders registry
        downgraders_registry = cls.app_manager.registry.get_registry("downgraders")

        for violation in violations:
            rule_id = violation["rule_id"]
            new_limit = violation["new_limit"]

            if downgraders_registry:
                downgrader = downgraders_registry.get(rule_id)
                if downgrader:
                    success = await downgrader(session, client_id, app_id, new_limit)
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

    # =========================================================================
    # JWT-Based Checking (Fast, no DB query)
    # =========================================================================

    @classmethod
    def check_subscription_from_claims(
        cls,
        claims: Dict[str, Any],
        client_id: str
    ) -> Dict[str, Any]:
        """
        Get subscription info from JWT claims.

        Args:
            claims: JWT claims dict (from info.context.claims)
            client_id: Client ID to check

        Returns:
            Subscription dict with plan_id, status, rules or empty dict

        Note:
            Does NOT raise errors - returns empty dict if not found.
            Use enforce_* methods for error handling.
        """
        subscriptions = claims.get("subscriptions", {})
        return subscriptions.get(client_id, {})

    @classmethod
    def check_quota_from_claims(
        cls,
        claims: Dict[str, Any],
        client_id: str,
        rule_id: str,
        current_count: int
    ) -> Tuple[bool, int, int]:
        """
        Check quota from JWT claims (no DB query).

        Args:
            claims: JWT claims dict
            client_id: Client ID
            rule_id: Rule ID (e.g., "MAX_USERS")
            current_count: Current usage count (caller must provide)

        Returns:
            Tuple of (is_valid, current_count, limit)
            limit = -1 means unlimited
        """
        subscription = cls.check_subscription_from_claims(claims, client_id)

        if not subscription:
            return (False, current_count, 0)

        rules = subscription.get("rules", {})
        limit = rules.get(rule_id)

        if limit is None:
            # Rule not in plan = unlimited
            return (True, current_count, -1)

        if isinstance(limit, bool):
            # This is a feature toggle, not a quota
            return (True, current_count, -1)

        # Quota check
        is_valid = current_count < limit
        return (is_valid, current_count, limit)

    @classmethod
    def enforce_quota_from_claims(
        cls,
        claims: Dict[str, Any],
        client_id: str,
        rule_id: str,
        current_count: int,
        error: Tuple[int, str] | None = None
    ) -> None:
        """
        Enforce quota from JWT claims - raises error if exceeded.

        Args:
            claims: JWT claims dict
            client_id: Client ID
            rule_id: Rule ID
            current_count: Current usage count
            error: Optional custom error tuple

        Raises:
            LysError: If quota exceeded or no subscription
        """
        subscription = cls.check_subscription_from_claims(claims, client_id)

        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Check subscription status
        status = subscription.get("status", "active")
        if status not in ("active", "pending"):
            raise LysError(
                SUBSCRIPTION_INACTIVE,
                f"Subscription is {status}"
            )

        is_valid, current, limit = cls.check_quota_from_claims(
            claims, client_id, rule_id, current_count
        )

        if not is_valid:
            raise LysError(
                error or QUOTA_EXCEEDED,
                f"Quota exceeded for {rule_id}: {current}/{limit}"
            )

    @classmethod
    def check_feature_from_claims(
        cls,
        claims: Dict[str, Any],
        client_id: str,
        rule_id: str
    ) -> bool:
        """
        Check feature availability from JWT claims (no DB query).

        Args:
            claims: JWT claims dict
            client_id: Client ID
            rule_id: Feature rule ID

        Returns:
            True if feature is available
        """
        subscription = cls.check_subscription_from_claims(claims, client_id)

        if not subscription:
            return False

        rules = subscription.get("rules", {})
        return rule_id in rules

    @classmethod
    def enforce_feature_from_claims(
        cls,
        claims: Dict[str, Any],
        client_id: str,
        rule_id: str
    ) -> None:
        """
        Enforce feature from JWT claims - raises error if not available.

        Args:
            claims: JWT claims dict
            client_id: Client ID
            rule_id: Feature rule ID

        Raises:
            LysError: If feature not available or no subscription
        """
        subscription = cls.check_subscription_from_claims(claims, client_id)

        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Check subscription status
        status = subscription.get("status", "active")
        if status not in ("active", "pending"):
            raise LysError(
                SUBSCRIPTION_INACTIVE,
                f"Subscription is {status}"
            )

        has_feature = cls.check_feature_from_claims(claims, client_id, rule_id)

        if not has_feature:
            raise LysError(
                FEATURE_NOT_AVAILABLE,
                f"Feature {rule_id} is not available in your plan"
            )

    @classmethod
    def get_limits_from_claims(
        cls,
        claims: Dict[str, Any],
        client_id: str
    ) -> Dict[str, Any]:
        """
        Get all rule limits from JWT claims (no DB query).

        Args:
            claims: JWT claims dict
            client_id: Client ID

        Returns:
            Dict mapping rule_id to limit info
        """
        subscription = cls.check_subscription_from_claims(claims, client_id)

        if not subscription:
            return {}

        rules = subscription.get("rules", {})
        limits = {}

        for rule_id, value in rules.items():
            if isinstance(value, bool):
                limits[rule_id] = {"enabled": value, "type": "feature"}
            else:
                limits[rule_id] = {"limit": value, "type": "quota"}

        return limits