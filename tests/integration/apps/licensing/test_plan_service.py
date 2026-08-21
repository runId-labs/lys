"""
Integration tests for licensing PlanService and PlanVersionService.

Tests cover:
- get_available_plans (global, custom, disabled exclusion)
- create_new_version (version increment, previous disabled)
- get_current_version
"""

import pytest
from uuid import uuid4

from lys.apps.licensing.consts import (
    DEFAULT_APPLICATION,
    FREE_PLAN,
    MAX_USERS,
    MONTHLY_PERIOD,
    PRO_PLAN,
    STARTER_PLAN,
    YEARLY_PERIOD,
)
from lys.core.errors import LysError
from tests.integration.apps.licensing.conftest import DEMO_QUOTA_RULE


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
                plan_id, session,
                prices=[{"period_id": MONTHLY_PERIOD, "amount": 1000}],
                rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
            )
            assert v1.version == 1
            assert v1.enabled is True
            await session.commit()

        # Create second version
        async with licensing_app_manager.database.get_session() as session:
            v2 = await version_service.create_new_version(
                plan_id, session,
                prices=[{"period_id": MONTHLY_PERIOD, "amount": 1500}],
                rules=[{"rule_id": MAX_USERS, "limit_value": 20}]
            )
            assert v2.version == 2
            assert v2.enabled is True
            await session.commit()

        # Verify first version is now disabled and the new price applies
        async with licensing_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(plan_id, session)
            assert current.version == 2
            assert current.price_for(MONTHLY_PERIOD).amount == 1500

    @pytest.mark.asyncio
    async def test_plan_version_is_free_property(self, licensing_app_manager):
        """Test LicensePlanVersion.is_free property."""
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            assert free_version.is_free is True

            starter_version = await version_service.get_current_version(STARTER_PLAN, session)
            assert starter_version.is_free is False


class TestPlanVersionAdministration:
    """The catalogue is published through the plan version services."""

    @pytest.mark.asyncio
    async def test_publish_a_priced_version_and_set_a_quota(self, licensing_app_manager):
        """
        A version is published complete: it becomes the offered one as soon as
        it exists, so its rules cannot wait for a second call.
        """
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"ADMIN_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )

            await version_service.create_new_version(
                plan_id, session,
                prices=[
                    {"period_id": MONTHLY_PERIOD, "amount": 2900},
                    {"period_id": YEARLY_PERIOD, "amount": 29000},
                ],
                rules=[{"rule_id": MAX_USERS, "limit_value": 50}]
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(plan_id, session)

            assert current.version == 1
            assert current.is_free is False
            assert current.price_for(MONTHLY_PERIOD).amount == 2900
            assert current.price_for(YEARLY_PERIOD).amount == 29000
            assert [(r.rule_id, r.limit_value) for r in current.rules] == [(MAX_USERS, 50)]

    @pytest.mark.asyncio
    async def test_free_version_needs_no_price(self, licensing_app_manager):
        """The free plan is versioned like any other, simply without a price."""
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"FREEISH_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            version = await version_service.create_new_version(
                plan_id, session,
                rules=[{"rule_id": MAX_USERS, "limit_value": 3}]
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(plan_id, session)
            assert current.id == version.id
            assert current.is_free is True

    @pytest.mark.asyncio
    async def test_enabling_a_version_disables_the_others(self, licensing_app_manager):
        """Only one version of a plan may be offered at a time."""
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"TOGGLE_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            v1 = await version_service.create_new_version(
                plan_id, session,
                prices=[{"period_id": MONTHLY_PERIOD, "amount": 1000}],
                rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
            )
            v2 = await version_service.create_new_version(
                plan_id, session,
                prices=[{"period_id": MONTHLY_PERIOD, "amount": 1500}],
                rules=[{"rule_id": MAX_USERS, "limit_value": 20}]
            )
            await session.commit()

        # v2 is the current one; putting v1 back must withdraw v2
        async with licensing_app_manager.database.get_session() as session:
            await version_service.set_enabled(v1.id, True, session)
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(plan_id, session)
            assert current.id == v1.id

            withdrawn = await version_service.get_by_id(v2.id, session)
            assert withdrawn.enabled is False

    @pytest.mark.asyncio
    async def test_set_enabled_on_unknown_version_raises(self, licensing_app_manager):
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError, match="PLAN_VERSION_NOT_FOUND"):
                await version_service.set_enabled(str(uuid4()), True, session)

    @pytest.mark.asyncio
    async def test_unknown_rule_is_rejected(self, licensing_app_manager):
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"BADRULE_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )

            with pytest.raises(LysError, match="UNKNOWN_RULE"):
                await version_service.create_new_version(
                    plan_id, session,
                    rules=[{"rule_id": "NOT_A_RULE", "limit_value": 5}]
                )

    @pytest.mark.asyncio
    async def test_rule_listed_twice_is_rejected(self, licensing_app_manager):
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"DUPRULE_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )

            with pytest.raises(LysError, match="DUPLICATE_RULE"):
                await version_service.create_new_version(
                    plan_id, session,
                    rules=[
                        {"rule_id": MAX_USERS, "limit_value": 5},
                        {"rule_id": MAX_USERS, "limit_value": 10},
                    ]
                )

    @pytest.mark.asyncio
    async def test_version_without_any_rule_is_rejected(self, licensing_app_manager):
        """
        An undeclared quota is read as unlimited by the checker, so a version
        granting nothing explicitly would grant everything.
        """
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"NORULE_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )

            with pytest.raises(LysError, match="NO_RULE_ON_VERSION"):
                await version_service.create_new_version(
                    plan_id, session,
                    prices=[{"period_id": MONTHLY_PERIOD, "amount": 2900}]
                )

    @pytest.mark.asyncio
    async def test_unlimited_is_expressed_with_a_null_limit(self, licensing_app_manager):
        """Unlimited has its own representation, so it stays deliberate."""
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")

        plan_id = f"UNLIMITED_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            await version_service.create_new_version(
                plan_id, session,
                rules=[{"rule_id": MAX_USERS, "limit_value": None}]
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            current = await version_service.get_current_version(plan_id, session)
            assert [(r.rule_id, r.limit_value) for r in current.rules] == [(MAX_USERS, None)]

    @pytest.mark.asyncio
    async def test_setting_an_unknown_rule_is_rejected_cleanly(self, licensing_app_manager):
        """
        The same mistake must surface the same way whether it is made when
        publishing a version or when correcting one afterwards.
        """
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")
        rule_service = licensing_app_manager.get_service("license_plan_version_rule")

        plan_id = f"SETRULE_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            version = await version_service.create_new_version(
                plan_id, session,
                rules=[{"rule_id": MAX_USERS, "limit_value": 5}]
            )

            with pytest.raises(LysError, match="UNKNOWN_RULE"):
                await rule_service.set_rule_limit(
                    plan_version_id=version.id,
                    rule_id="NOT_A_RULE",
                    limit_value=5,
                    session=session
                )

    @pytest.mark.asyncio
    async def test_setting_a_rule_on_an_unknown_version_is_rejected(self, licensing_app_manager):
        rule_service = licensing_app_manager.get_service("license_plan_version_rule")

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError, match="PLAN_VERSION_NOT_FOUND"):
                await rule_service.set_rule_limit(
                    plan_version_id=str(uuid4()),
                    rule_id=MAX_USERS,
                    limit_value=5,
                    session=session
                )


class TestLicensePlanVersionRuleServiceGetRulesForVersionSync:
    """Test LicensePlanVersionRuleService.get_rules_for_version_sync (Celery contexts)."""

    @pytest.mark.asyncio
    async def test_returns_the_rules_configured_for_the_version(self, licensing_app_manager):
        rule_service = licensing_app_manager.get_service("license_plan_version_rule")
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)

        with licensing_app_manager.database.get_sync_session() as session:
            rules = rule_service.get_rules_for_version_sync(free_version.id, session)

        rules_by_id = {r.rule_id: r.limit_value for r in rules}
        assert rules_by_id == {MAX_USERS: 5, DEMO_QUOTA_RULE: 3}

    @pytest.mark.asyncio
    async def test_returns_empty_for_an_unknown_version(self, licensing_app_manager):
        rule_service = licensing_app_manager.get_service("license_plan_version_rule")

        with licensing_app_manager.database.get_sync_session() as session:
            rules = rule_service.get_rules_for_version_sync(str(uuid4()), session)

        assert rules == []
