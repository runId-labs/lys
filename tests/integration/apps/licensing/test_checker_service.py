"""
Integration tests for licensing LicenseCheckerService.

Tests cover:
- check_feature / enforce_feature (present/absent in plan)
- get_client_limits
- check_quota / enforce_quota
- validate_downgrade

Note: create_client_with_owner automatically creates a FREE plan subscription
via the licensing ClientService extension.
"""

import pytest
from uuid import uuid4

from lys.apps.licensing.consts import (
    FREE_PLAN, STARTER_PLAN, PRO_PLAN, MAX_USERS, MAX_PROJECTS_PER_MONTH,
    DEFAULT_APPLICATION,
)
from lys.core.errors import LysError


class TestLicenseCheckerServiceFeatures:
    """Test LicenseCheckerService feature check methods."""

    @pytest.mark.asyncio
    async def test_check_feature_present(self, licensing_app_manager):
        """Test that check_feature returns True for a feature present in plan."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Feat-Corp-{uuid4().hex[:8]}",
                email=f"feat-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # MAX_USERS is a rule in FREE plan (auto-subscribed)
        async with licensing_app_manager.database.get_session() as session:
            has_feature = await checker_service.check_feature(client.id, MAX_USERS, session)
            assert has_feature is True

    @pytest.mark.asyncio
    async def test_check_feature_absent(self, licensing_app_manager):
        """Test that check_feature returns False for a feature not in plan."""
        checker_service = licensing_app_manager.get_service("license_checker")
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"NoFeat-Corp-{uuid4().hex[:8]}",
                email=f"nofeat-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Upgrade to PRO plan (no MAX_PROJECTS_PER_MONTH rule)
        async with licensing_app_manager.database.get_session() as session:
            pro_version = await version_service.get_current_version(PRO_PLAN, session)
            await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=pro_version.id,
                session=session,
                immediate=True
            )

        async with licensing_app_manager.database.get_session() as session:
            has_feature = await checker_service.check_feature(
                client.id, MAX_PROJECTS_PER_MONTH, session
            )
            assert has_feature is False

    @pytest.mark.asyncio
    async def test_enforce_feature_absent_raises(self, licensing_app_manager):
        """Test that enforce_feature raises error when feature is absent."""
        checker_service = licensing_app_manager.get_service("license_checker")
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Enforce-Corp-{uuid4().hex[:8]}",
                email=f"enforce-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Upgrade to PRO plan (no MAX_PROJECTS_PER_MONTH rule)
        async with licensing_app_manager.database.get_session() as session:
            pro_version = await version_service.get_current_version(PRO_PLAN, session)
            await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=pro_version.id,
                session=session,
                immediate=True
            )

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await checker_service.enforce_feature(
                    client.id, MAX_PROJECTS_PER_MONTH, session
                )
            assert "FEATURE_NOT_AVAILABLE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_feature_no_subscription_raises(self, licensing_app_manager):
        """Test that check_feature raises when client has no subscription."""
        checker_service = licensing_app_manager.get_service("license_checker")

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await checker_service.check_feature(str(uuid4()), MAX_USERS, session)
            assert "NO_ACTIVE_SUBSCRIPTION" in str(exc_info.value)


class TestLicenseCheckerServiceLimits:
    """Test LicenseCheckerService.get_client_limits."""

    @pytest.mark.asyncio
    async def test_get_client_limits(self, licensing_app_manager):
        """Test getting all limits for a client's plan."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Limits-Corp-{uuid4().hex[:8]}",
                email=f"limits-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Client auto-subscribed to FREE plan
        async with licensing_app_manager.database.get_session() as session:
            limits = await checker_service.get_client_limits(client.id, session)

            assert MAX_USERS in limits
            assert limits[MAX_USERS]["limit"] == 5
            assert limits[MAX_USERS]["type"] == "quota"
            assert MAX_PROJECTS_PER_MONTH in limits
            assert limits[MAX_PROJECTS_PER_MONTH]["limit"] == 3

    @pytest.mark.asyncio
    async def test_get_client_limits_no_subscription_raises(self, licensing_app_manager):
        """Test that get_client_limits raises when no subscription."""
        checker_service = licensing_app_manager.get_service("license_checker")

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await checker_service.get_client_limits(str(uuid4()), session)
            assert "NO_ACTIVE_SUBSCRIPTION" in str(exc_info.value)


# ==============================================================================
# Phase 1A: check_quota and enforce_quota tests
# ==============================================================================


class TestLicenseCheckerServiceQuota:
    """Test LicenseCheckerService.check_quota and enforce_quota."""

    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self, licensing_app_manager):
        """Test check_quota returns valid when under limit."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Quota-Corp-{uuid4().hex[:8]}",
                email=f"quota-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # FREE plan has MAX_USERS=5, no users added yet so should be valid
        async with licensing_app_manager.database.get_session() as session:
            is_valid, current, limit = await checker_service.check_quota(
                client.id, MAX_USERS, session
            )
            assert is_valid is True
            assert current >= 0
            assert limit == 5

    @pytest.mark.asyncio
    async def test_check_quota_rule_not_in_plan(self, licensing_app_manager):
        """Test check_quota returns valid with -1 limit when rule not in plan."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"NoRule-Corp-{uuid4().hex[:8]}",
                email=f"norule-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Upgrade to PRO plan (no MAX_PROJECTS_PER_MONTH rule)
        async with licensing_app_manager.database.get_session() as session:
            pro_version = await version_service.get_current_version(PRO_PLAN, session)
            await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=pro_version.id,
                session=session,
                immediate=True
            )

        async with licensing_app_manager.database.get_session() as session:
            is_valid, current, limit = await checker_service.check_quota(
                client.id, MAX_PROJECTS_PER_MONTH, session
            )
            # Rule not configured = unlimited
            assert is_valid is True
            assert limit == -1

    @pytest.mark.asyncio
    async def test_check_quota_no_subscription_raises(self, licensing_app_manager):
        """Test check_quota raises error when no subscription exists."""
        checker_service = licensing_app_manager.get_service("license_checker")

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await checker_service.check_quota(str(uuid4()), MAX_USERS, session)
            assert "NO_ACTIVE_SUBSCRIPTION" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_enforce_quota_within_limit(self, licensing_app_manager):
        """Test enforce_quota does not raise when within limit."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"EnforceOK-Corp-{uuid4().hex[:8]}",
                email=f"enforceok-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Should not raise (within limit)
        async with licensing_app_manager.database.get_session() as session:
            await checker_service.enforce_quota(client.id, MAX_USERS, session)


# ==============================================================================
# Phase 1A: validate_downgrade tests
# ==============================================================================


class TestLicenseCheckerServiceDowngrade:
    """Test LicenseCheckerService.validate_downgrade."""

    @pytest.mark.asyncio
    async def test_validate_downgrade_no_violations(self, licensing_app_manager):
        """Test validate_downgrade returns empty list when no violations."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Downgrade-Corp-{uuid4().hex[:8]}",
                email=f"downgrade-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Validate downgrade from FREE to FREE (same version, no violations)
        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            violations = await checker_service.validate_downgrade(
                client.id, free_version.id, session
            )
            assert isinstance(violations, list)
            assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_validate_downgrade_no_subscription(self, licensing_app_manager):
        """Test validate_downgrade returns empty list when no subscription."""
        checker_service = licensing_app_manager.get_service("license_checker")
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            violations = await checker_service.validate_downgrade(
                str(uuid4()), free_version.id, session
            )
            assert isinstance(violations, list)
            assert len(violations) == 0
