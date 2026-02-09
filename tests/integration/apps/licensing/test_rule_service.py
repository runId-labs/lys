"""
Integration tests for LicenseRuleService and rule validators.

Tests cover:
- LicenseRuleService CRUD (get, list rules)
- validate_max_users validator
- validate_max_projects_per_month validator (placeholder)
"""

import pytest
from uuid import uuid4

from lys.apps.licensing.consts import MAX_USERS, MAX_PROJECTS_PER_MONTH


class TestLicenseRuleServiceCRUD:
    """Test LicenseRuleService basic operations."""

    @pytest.mark.asyncio
    async def test_get_rule_by_id(self, licensing_app_manager):
        """Test getting a rule by its ID."""
        rule_service = licensing_app_manager.get_service("license_rule")

        async with licensing_app_manager.database.get_session() as session:
            rule = await rule_service.get_by_id(MAX_USERS, session)
            assert rule is not None
            assert rule.id == MAX_USERS
            assert rule.enabled is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_rule(self, licensing_app_manager):
        """Test getting a nonexistent rule returns None."""
        rule_service = licensing_app_manager.get_service("license_rule")

        async with licensing_app_manager.database.get_session() as session:
            rule = await rule_service.get_by_id("NONEXISTENT_RULE", session)
            assert rule is None

    @pytest.mark.asyncio
    async def test_list_rules(self, licensing_app_manager):
        """Test listing all rules returns seeded rules."""
        rule_service = licensing_app_manager.get_service("license_rule")

        async with licensing_app_manager.database.get_session() as session:
            from sqlalchemy import select
            entity = licensing_app_manager.get_entity("license_rule")
            result = await session.execute(select(entity))
            rules = list(result.scalars().all())

            assert len(rules) >= 2
            rule_ids = {r.id for r in rules}
            assert MAX_USERS in rule_ids
            assert MAX_PROJECTS_PER_MONTH in rule_ids


class TestValidateMaxUsers:
    """Test validate_max_users validator via check_quota."""

    @pytest.mark.asyncio
    async def test_validate_max_users_within_limit(self, licensing_app_manager):
        """Test MAX_USERS validator returns valid when under limit."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"ValUser-Corp-{uuid4().hex[:8]}",
                email=f"valuser-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # FREE plan has MAX_USERS=5, no extra users added
        async with licensing_app_manager.database.get_session() as session:
            is_valid, current, limit = await checker_service.check_quota(
                client.id, MAX_USERS, session
            )
            assert is_valid is True
            assert limit == 5
            # current should be the count of subscription_users
            assert current >= 0


class TestValidateMaxProjectsPerMonth:
    """Test validate_max_projects_per_month validator (placeholder)."""

    @pytest.mark.asyncio
    async def test_validate_max_projects_per_month_within_limit(self, licensing_app_manager):
        """Test MAX_PROJECTS_PER_MONTH validator returns valid (placeholder)."""
        checker_service = licensing_app_manager.get_service("license_checker")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"ValProj-Corp-{uuid4().hex[:8]}",
                email=f"valproj-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # FREE plan has MAX_PROJECTS_PER_MONTH=3
        async with licensing_app_manager.database.get_session() as session:
            is_valid, current, limit = await checker_service.check_quota(
                client.id, MAX_PROJECTS_PER_MONTH, session
            )
            # Placeholder validator always returns valid
            assert is_valid is True
            assert limit == 3
