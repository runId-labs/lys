"""
Integration tests for the licensing Celery tasks.

These exercise `apply_pending_plan_changes` end to end, on the synchronous
engine it actually runs on. That path was previously unreachable from the tests:
the manager builds one engine per driver from the same setting, and a ":memory:"
database gives each of them a database of its own, so the task opened an empty
schema and did nothing. The licensing fixture uses a temporary file instead,
which is what makes these assertions mean anything.

Covered here:
- Tacit renewal removing the discount granted against the commitment
- Realignment of the provider once the discount ends
- Denunciation: a pending change reaching its term drops the discount too
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from lys.apps.licensing.consts import (
    DEFAULT_APPLICATION,
    MANUAL_GRANT,
    MAX_USERS,
    PERCENT_UNIT,
    PROVIDER_BILLING,
    YEARLY_PERIOD,
)


class _TaskCeleryApp:
    """Stand-in for the Celery app the task reads its manager from."""

    def __init__(self, app_manager):
        self.app_manager = app_manager


async def _committed_client_with_discount(
    licensing_app_manager,
    amount=30000,
    renewal_months=12,
    collected_by_provider=False,
):
    """A client on a committed price whose term has passed, benefiting from -30%.

    The commitment end date is placed in the past, which is what the task
    selects on: the subscription is picked up on its next run.

    Returns:
        The client id.
    """
    client_service = licensing_app_manager.get_service("client")
    plan_service = licensing_app_manager.get_service("license_plan")
    version_service = licensing_app_manager.get_service("license_plan_version")
    commitment_service = licensing_app_manager.get_service("license_commitment")
    price_service = licensing_app_manager.get_service("license_plan_version_price")
    discount_service = licensing_app_manager.get_service("license_discount")
    subscription_service = licensing_app_manager.get_service("subscription")

    suffix = uuid4().hex[:6]
    commitment_id = f"TASK_COMMIT_{suffix}"
    plan_id = f"TASK_PLAN_{suffix}"
    discount_id = f"TASK_DISC_{suffix}"

    async with licensing_app_manager.database.get_session() as session:
        client = await client_service.create_client_with_owner(
            session=session,
            client_name=f"Task-Corp-{uuid4().hex[:8]}",
            email=f"task-{uuid4().hex[:8]}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False
        )
        await commitment_service.create(
            session=session, id=commitment_id, enabled=True,
            duration_months=12, renewal_months=renewal_months, notice_months=3
        )
        await plan_service.create(
            session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
        )
        version = await version_service.create_new_version(
            plan_id, session,
            prices=[{
                "period_id": YEARLY_PERIOD,
                "amount": amount,
                "commitment_id": commitment_id,
            }],
            rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
        )
        await discount_service.create(
            session=session,
            id=discount_id,
            enabled=True,
            value=30,
            unit_id=PERCENT_UNIT,
            grant_id=MANUAL_GRANT,
            description="Thirty percent off",
        )
        prices = await price_service.get_all(session)
        price = next(p for p in prices if p.plan_version_id == version.id)

        subscription = await subscription_service.get_client_subscription(client.id, session)
        # Granted in the same move: the price relationship still resolves to the
        # previous one at this point, and settling on it would owe nothing
        await subscription_service.subscribe_manually(
            subscription=subscription,
            plan_version_price_id=price.id,
            session=session,
            discount_id=discount_id
        )

        # The term has passed: this is what the task selects on
        subscription.commitment_end_date = datetime.now(timezone.utc) - timedelta(days=1)

        if collected_by_provider:
            client.provider_customer_id = f"cst_{uuid4().hex[:8]}"
            subscription.provider_subscription_id = f"sub_{uuid4().hex[:8]}"
            subscription.billing_mode_id = PROVIDER_BILLING

        client_id = client.id
        await session.commit()

    return client_id


def _run_task(licensing_app_manager):
    """Run the task against the test manager, on its synchronous engine."""
    # Imported here, not at module level: the task module pulls in the licensing
    # entities, which would register themselves in the shared SQLAlchemy metadata
    # as soon as this file is collected. Test files loaded in the same process
    # without the licensing app would then fail to resolve their foreign keys.
    from lys.apps.licensing.tasks import apply_pending_plan_changes

    with patch(
        "lys.apps.licensing.tasks.current_app",
        _TaskCeleryApp(licensing_app_manager)
    ):
        return apply_pending_plan_changes()


class TestCommitmentRenewalTask:
    """What the daily task does when a commitment reaches its term."""

    @pytest.mark.asyncio
    async def test_the_renewal_drops_the_discount_and_restores_the_catalogue_price(
        self, licensing_app_manager
    ):
        """A discount is granted against a commitment and does not outlive it."""
        subscription_service = licensing_app_manager.get_service("subscription")

        client_id = await _committed_client_with_discount(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)
            assert subscription.amount_due == 21000
            lapsed_term = subscription.commitment_end_date

        _run_task(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)

            assert await subscription_service.get_granted_discount(subscription, session) is None
            assert subscription.amount_due == 30000
            assert subscription.receipt["discount"] is None
            assert subscription.receipt["amount_due"] == 30000
            # Renewed rather than ended: the term moved a year forward. Both dates
            # come back from SQLite without a timezone, so they compare as stored.
            assert subscription.commitment_end_date.year == lapsed_term.year + 1
            assert subscription.commitment_end_date.month == lapsed_term.month

    @pytest.mark.asyncio
    async def test_a_commitment_that_simply_ends_also_drops_the_discount(
        self, licensing_app_manager
    ):
        """No renewal span means the commitment ends — the discount ends with it."""
        subscription_service = licensing_app_manager.get_service("subscription")

        client_id = await _committed_client_with_discount(
            licensing_app_manager, renewal_months=0
        )

        _run_task(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)

            assert subscription.commitment_end_date is None
            assert await subscription_service.get_granted_discount(subscription, session) is None
            assert subscription.amount_due == 30000

    @pytest.mark.asyncio
    async def test_the_renewal_realigns_the_provider_on_the_catalogue_price(
        self, licensing_app_manager
    ):
        """The provider knows nothing of the discount and would keep collecting it."""
        client_id = await _committed_client_with_discount(
            licensing_app_manager, collected_by_provider=True
        )

        with patch(
            "lys.apps.licensing.modules.mollie.services."
            "MollieCheckoutService.update_subscription_amount"
        ) as update:
            _run_task(licensing_app_manager)

            update.assert_called_once()
            assert update.call_args.kwargs["value"] == "300.00"

    @pytest.mark.asyncio
    async def test_nothing_is_pushed_when_the_amount_does_not_move(
        self, licensing_app_manager
    ):
        """A renewal without a discount changes nothing to collect."""
        subscription_service = licensing_app_manager.get_service("subscription")

        client_id = await _committed_client_with_discount(
            licensing_app_manager, collected_by_provider=True
        )

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)
            await subscription_service.revoke_discount(subscription, session)
            await session.commit()

        with patch(
            "lys.apps.licensing.modules.mollie.services."
            "MollieCheckoutService.update_subscription_amount"
        ) as update:
            _run_task(licensing_app_manager)

            update.assert_not_called()


class TestDenouncedCommitmentTask:
    """A denounced commitment leaves the renewal loop, and must still lose its discount."""

    @pytest.mark.asyncio
    async def test_a_denounced_commitment_drops_the_discount_too(
        self, licensing_app_manager
    ):
        """The pending-change loop is the only occasion left to remove it.

        A subscription carrying a pending change is excluded from the renewal
        loop, and applying the change clears the term for good: without a drop
        here the discount would follow the client onto the new plan forever.
        """
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        plan_service = licensing_app_manager.get_service("license_plan")

        client_id = await _committed_client_with_discount(licensing_app_manager)

        suffix = uuid4().hex[:6]
        target_plan_id = f"TASK_TARGET_{suffix}"

        async with licensing_app_manager.database.get_session() as session:
            await plan_service.create(
                session=session, id=target_plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            target_version = await version_service.create_new_version(
                target_plan_id, session,
                rules=[{"rule_id": MAX_USERS, "limit_value": 5}]
            )

            subscription = await subscription_service.get_client_subscription(client_id, session)
            subscription.pending_plan_version_id = target_version.id
            target_version_id = target_version.id
            await session.commit()

        _run_task(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)

            assert subscription.plan_version_id == target_version_id
            assert subscription.pending_plan_version_id is None
            assert subscription.commitment_end_date is None
            # The discount does not follow the client onto the new plan
            assert await subscription_service.get_granted_discount(subscription, session) is None
            # The target plan is free: nothing is owed, and the receipt says so
            assert subscription.amount_due is None
            assert subscription.receipt is None
