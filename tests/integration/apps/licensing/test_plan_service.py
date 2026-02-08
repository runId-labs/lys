"""
Integration tests for licensing PlanService and PlanVersionService.

Tests cover:
- get_available_plans (global, custom, disabled exclusion)
- create_new_version (version increment, previous disabled)
- get_current_version
"""

import pytest
from uuid import uuid4

from lys.apps.licensing.consts import FREE_PLAN, STARTER_PLAN, PRO_PLAN, DEFAULT_APPLICATION


class TestLicensePlanServiceAvailablePlans:
    """Test LicensePlanService.get_available_plans."""

    @pytest.mark.asyncio
    async def test_get_available_plans_global(self, licensing_app_manager):
        """Test getting all global enabled plans."""
        plan_service = licensing_app_manager.get_service("license_plan")

        async with licensing_app_manager.database.get_session() as session:
            plans = await plan_service.get_available_plans(session)

            plan_ids = {p.id for p in plans}
            assert FREE_PLAN in plan_ids
            assert STARTER_PLAN in plan_ids
            assert PRO_PLAN in plan_ids

    @pytest.mark.asyncio
    async def test_get_available_plans_with_client_id(self, licensing_app_manager):
        """Test getting plans including custom plans for a client."""
        plan_service = licensing_app_manager.get_service("license_plan")
        client_service = licensing_app_manager.get_service("client")

        # Create a client
        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"CustomPlan-Corp-{uuid4().hex[:8]}",
                email=f"custom-plan-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create a custom plan for this client
        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=f"CUSTOM_{uuid4().hex[:6]}",
                enabled=True, app_id=DEFAULT_APPLICATION,
                client_id=client.id
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            plans = await plan_service.get_available_plans(session, client_id=client.id)
            # Should include global plans + custom plan
            assert len(plans) >= 4

    @pytest.mark.asyncio
    async def test_get_available_plans_excludes_disabled(self, licensing_app_manager):
        """Test that disabled plans are excluded."""
        plan_service = licensing_app_manager.get_service("license_plan")

        # Create a disabled plan
        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=f"DISABLED_{uuid4().hex[:6]}",
                enabled=False, app_id=DEFAULT_APPLICATION
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            plans = await plan_service.get_available_plans(session)
            plan_ids = {p.id for p in plans}
            # Should not contain any disabled plan
            for plan_id in plan_ids:
                assert not plan_id.startswith("DISABLED_")


class TestLicensePlanVersionService:
    """Test LicensePlanVersionService operations."""

    @pytest.mark.asyncio
    async def test_get_current_version(self, licensing_app_manager):
        """Test getting the current enabled version for a plan."""
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            version = await version_service.get_current_version(FREE_PLAN, session)
            assert version is not None
            assert version.plan_id == FREE_PLAN
            assert version.enabled is True
            assert version.version == 1

    @pytest.mark.asyncio
    async def test_get_current_version_nonexistent_plan(self, licensing_app_manager):
        """Test getting version for a plan with no versions returns None."""
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            version = await version_service.get_current_version("NONEXISTENT", session)
            assert version is None

    @pytest.mark.asyncio
    async def test_create_new_version_increments(self, licensing_app_manager):
        """Test that creating a new version increments version number."""
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        # Create a test plan
        plan_id = f"VERSION_TEST_{uuid4().hex[:6]}"
        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True,
                app_id=DEFAULT_APPLICATION
            )
            # Create first version
            v1 = await version_service.create_new_version(
                plan_id, session, price_monthly=1000
            )
            assert v1.version == 1
            assert v1.enabled is True
            await session.commit()

        # Create second version
        async with licensing_app_manager.database.get_session() as session:
            v2 = await version_service.create_new_version(
                plan_id, session, price_monthly=1500
            )
            assert v2.version == 2
            assert v2.enabled is True
            await session.commit()

        # Verify first version is now disabled
        async with licensing_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(plan_id, session)
            assert current.version == 2
            assert current.price_monthly == 1500

    @pytest.mark.asyncio
    async def test_plan_version_is_free_property(self, licensing_app_manager):
        """Test LicensePlanVersion.is_free property."""
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            assert free_version.is_free is True

            starter_version = await version_service.get_current_version(STARTER_PLAN, session)
            assert starter_version.is_free is False
