"""
Integration tests for licensing SubscriptionService.

Tests cover:
- create_subscription (via create_client_with_owner auto-subscription)
- get_client_subscription
- change_plan (immediate, deferred)
- apply_pending_change
- User management (add, remove, count, is_licensed)

Note: create_client_with_owner automatically creates a FREE plan subscription
via the licensing ClientService extension.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from lys.apps.licensing.consts import (
    BILLING_TERMS_CHANGE_ERROR,
    NOTICE_PERIOD_EXPIRED_ERROR,
    DEFAULT_APPLICATION,
    EUR_CURRENCY,
    FREE_PLAN,
    MAX_USERS,
    MONTHLY_PERIOD,
    PLAN_NOT_PRICED_ERROR,
    PRO_PLAN,
    STARTER_PLAN,
    YEARLY_PERIOD,
)
from lys.core.errors import LysError


class TestSubscriptionServiceCreate:
    """Test SubscriptionService subscription creation."""

    @pytest.mark.asyncio
    async def test_create_client_with_owner_auto_subscribes(self, licensing_app_manager):
        """Test that create_client_with_owner automatically creates a FREE subscription."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Sub-Corp-{uuid4().hex[:8]}",
                email=f"sub-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client.id, session)

            assert subscription is not None
            assert subscription.client_id == client.id
            assert subscription.is_free is True

    @pytest.mark.asyncio
    async def test_create_subscription_duplicate_fails(self, licensing_app_manager):
        """Test that creating a duplicate subscription raises error."""
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Dup-Corp-{uuid4().hex[:8]}",
                email=f"dup-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Client already has an auto-created FREE subscription
        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            with pytest.raises(LysError) as exc_info:
                await subscription_service.create_subscription(
                    client_id=client.id,
                    plan_version_id=free_version.id,
                    session=session
                )
            assert "SUBSCRIPTION_ALREADY_EXISTS" in str(exc_info.value)


class TestSubscriptionServiceGetAndChange:
    """Test SubscriptionService get and change operations."""

    @pytest.mark.asyncio
    async def test_get_client_subscription(self, licensing_app_manager):
        """Test retrieving a client's subscription."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Get-Corp-{uuid4().hex[:8]}",
                email=f"get-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client.id, session)
            assert subscription is not None
            assert subscription.client_id == client.id

    @pytest.mark.asyncio
    async def test_get_client_subscription_none(self, licensing_app_manager):
        """Test that a client without subscription returns None."""
        subscription_service = licensing_app_manager.get_service("subscription")

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(
                str(uuid4()), session
            )
            assert subscription is None

    @pytest.mark.asyncio
    async def test_change_plan_immediate(self, licensing_app_manager):
        """Test changing plan immediately."""
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Change-Corp-{uuid4().hex[:8]}",
                email=f"change-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Client auto-subscribed to FREE, change to STARTER
        async with licensing_app_manager.database.get_session() as session:
            starter_version = await version_service.get_current_version(STARTER_PLAN, session)
            subscription = await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=starter_version.id,
                session=session,
                immediate=True
            )

            assert subscription.plan_version_id == starter_version.id
            assert subscription.pending_plan_version_id is None

    @pytest.mark.asyncio
    async def test_change_plan_deferred(self, licensing_app_manager):
        """Test scheduling a plan change for period end."""
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Defer-Corp-{uuid4().hex[:8]}",
                email=f"defer-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # First upgrade to STARTER immediately
        async with licensing_app_manager.database.get_session() as session:
            starter_version = await version_service.get_current_version(STARTER_PLAN, session)
            await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=starter_version.id,
                session=session,
                immediate=True
            )

        # Now schedule deferred downgrade to FREE
        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            starter_version = await version_service.get_current_version(STARTER_PLAN, session)

            subscription = await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=free_version.id,
                session=session,
                immediate=False
            )

            assert subscription.plan_version_id == starter_version.id  # Still on starter
            assert subscription.pending_plan_version_id == free_version.id
            assert subscription.has_pending_downgrade is True

    @pytest.mark.asyncio
    async def test_change_plan_no_subscription_fails(self, licensing_app_manager):
        """Test that changing plan without subscription raises error."""
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")

        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            with pytest.raises(LysError) as exc_info:
                await subscription_service.change_plan(
                    client_id=str(uuid4()),
                    new_plan_version_id=free_version.id,
                    session=session
                )
            assert "NO_ACTIVE_SUBSCRIPTION" in str(exc_info.value)


class TestSubscriptionServiceApplyPendingChange:
    """Test SubscriptionService.apply_pending_change."""

    @pytest.mark.asyncio
    async def test_apply_pending_change(self, licensing_app_manager):
        """Test applying a pending plan change."""
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Apply-Corp-{uuid4().hex[:8]}",
                email=f"apply-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Upgrade to STARTER first
        async with licensing_app_manager.database.get_session() as session:
            starter_version = await version_service.get_current_version(STARTER_PLAN, session)
            await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=starter_version.id,
                session=session,
                immediate=True
            )

        # Set deferred downgrade to FREE
        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            sub = await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=free_version.id,
                session=session,
                immediate=False
            )

        # Apply pending change
        async with licensing_app_manager.database.get_session() as session:
            result = await subscription_service.apply_pending_change(sub.id, session)
            assert result is not None
            assert result.pending_plan_version_id is None

    @pytest.mark.asyncio
    async def test_apply_pending_change_no_pending(self, licensing_app_manager):
        """Test that apply_pending_change returns None when no pending change."""
        subscription_service = licensing_app_manager.get_service("subscription")

        async with licensing_app_manager.database.get_session() as session:
            result = await subscription_service.apply_pending_change(str(uuid4()), session)
            assert result is None


class TestSubscriptionServiceUserManagement:
    """Test SubscriptionService user management."""

    @pytest.mark.asyncio
    async def test_add_user_to_subscription(self, licensing_app_manager):
        """Test adding a user to a subscription."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")
        user_service = licensing_app_manager.get_service("user")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"UserMgmt-Corp-{uuid4().hex[:8]}",
                email=f"usermgmt-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            sub = await subscription_service.get_client_subscription(client.id, session)
            user = await user_service.create_user(
                session=session,
                email=f"licensed-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await subscription_service.add_user_to_subscription(sub.id, user.id, session)

            count = await subscription_service.get_subscription_user_count(sub.id, session)
            assert count == 1

    @pytest.mark.asyncio
    async def test_add_user_duplicate_fails(self, licensing_app_manager):
        """Test that adding a user twice raises error."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")
        user_service = licensing_app_manager.get_service("user")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"DupUser-Corp-{uuid4().hex[:8]}",
                email=f"dupuser-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            sub = await subscription_service.get_client_subscription(client.id, session)
            user = await user_service.create_user(
                session=session,
                email=f"duplic-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await subscription_service.add_user_to_subscription(sub.id, user.id, session)

            with pytest.raises(LysError) as exc_info:
                await subscription_service.add_user_to_subscription(sub.id, user.id, session)
            assert "USER_ALREADY_LICENSED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_remove_user_from_subscription(self, licensing_app_manager):
        """Test removing a user from a subscription."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")
        user_service = licensing_app_manager.get_service("user")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"RemUser-Corp-{uuid4().hex[:8]}",
                email=f"remuser-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            sub = await subscription_service.get_client_subscription(client.id, session)
            user = await user_service.create_user(
                session=session,
                email=f"remove-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await subscription_service.add_user_to_subscription(sub.id, user.id, session)
            await subscription_service.remove_user_from_subscription(sub.id, user.id, session)

            count = await subscription_service.get_subscription_user_count(sub.id, session)
            assert count == 0

    @pytest.mark.asyncio
    async def test_remove_user_not_licensed_fails(self, licensing_app_manager):
        """Test that removing a non-licensed user raises error."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"NotLic-Corp-{uuid4().hex[:8]}",
                email=f"notlic-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            sub = await subscription_service.get_client_subscription(client.id, session)

            with pytest.raises(LysError) as exc_info:
                await subscription_service.remove_user_from_subscription(
                    sub.id, str(uuid4()), session
                )
            assert "USER_NOT_LICENSED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_is_user_licensed(self, licensing_app_manager):
        """Test checking if a user is licensed."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")
        user_service = licensing_app_manager.get_service("user")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"IsLic-Corp-{uuid4().hex[:8]}",
                email=f"islic-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            sub = await subscription_service.get_client_subscription(client.id, session)
            user = await user_service.create_user(
                session=session,
                email=f"islic-user-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

            # Not licensed yet
            assert await subscription_service.is_user_licensed(user.id, session) is False

            # Add user
            await subscription_service.add_user_to_subscription(sub.id, user.id, session)

            # Now licensed
            assert await subscription_service.is_user_licensed(user.id, session) is True

    @pytest.mark.asyncio
    async def test_get_subscription_user_count(self, licensing_app_manager):
        """Test getting the user count for a subscription."""
        subscription_service = licensing_app_manager.get_service("subscription")
        client_service = licensing_app_manager.get_service("client")
        user_service = licensing_app_manager.get_service("user")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Count-Corp-{uuid4().hex[:8]}",
                email=f"count-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            sub = await subscription_service.get_client_subscription(client.id, session)

            assert await subscription_service.get_subscription_user_count(sub.id, session) == 0

            for i in range(3):
                user = await user_service.create_user(
                    session=session,
                    email=f"count-user-{i}-{uuid4().hex[:8]}@example.com",
                    password="Password123!",
                    language_id="en",
                    send_verification_email=False
                )
                await subscription_service.add_user_to_subscription(sub.id, user.id, session)

            assert await subscription_service.get_subscription_user_count(sub.id, session) == 3


class TestSubscribeToPlanPricingGuard:
    """Test that subscribe_to_plan refuses terms the target version is not priced for."""

    @pytest.mark.asyncio
    async def test_unknown_currency_is_rejected(self, licensing_app_manager):
        """
        An unpriced (period, currency) must not resolve to a free plan change.

        Without the guard, both the current and the target price resolve to 0,
        the request falls through to the downgrade branch, and the client is
        granted the paid plan at period end without paying.
        """
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Guard-Corp-{uuid4().hex[:8]}",
                email=f"guard-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            pro_version = await version_service.get_current_version(PRO_PLAN, session)

            result = await subscription_service.subscribe_to_plan(
                client_id=client.id,
                plan_version_id=pro_version.id,
                billing_period=MONTHLY_PERIOD,
                success_url="https://example.com/success",
                webhook_url="https://example.com/webhooks/mollie",
                session=session,
                currency_id="XXX"
            )

            assert result.success is False
            assert result.error == PLAN_NOT_PRICED_ERROR

            # No plan change was scheduled
            subscription = await subscription_service.get_client_subscription(client.id, session)
            assert subscription.pending_plan_version_id is None

    @pytest.mark.asyncio
    async def test_unpriced_period_is_rejected(self, licensing_app_manager):
        """Same guard applies when the version carries no price for the period."""
        subscription_service = licensing_app_manager.get_service("subscription")
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        plan_id = f"MONTHLY_ONLY_{uuid4().hex[:6]}"
        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Period-Corp-{uuid4().hex[:8]}",
                email=f"period-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            # Priced monthly only
            version = await version_service.create_new_version(
                plan_id, session,
                prices=[{"period_id": MONTHLY_PERIOD, "amount": 2500}],
                rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            result = await subscription_service.subscribe_to_plan(
                client_id=client.id,
                plan_version_id=version.id,
                billing_period=YEARLY_PERIOD,
                success_url="https://example.com/success",
                webhook_url="https://example.com/webhooks/mollie",
                session=session
            )

            assert result.success is False
            assert result.error == PLAN_NOT_PRICED_ERROR


class TestSubscribeToPlanBillingTerms:
    """Changing periodicity or currency mid-subscription is refused."""

    @pytest.mark.asyncio
    async def test_period_change_is_rejected(self, licensing_app_manager):
        """
        Prorata assumes both prices share a cadence, so a monthly to yearly
        switch would bill a meaningless amount. It must be refused, not guessed.
        """
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        price_service = licensing_app_manager.get_service("license_plan_version_price")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Terms-Corp-{uuid4().hex[:8]}",
                email=f"terms-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Put the client on a paid monthly subscription
        async with licensing_app_manager.database.get_session() as session:
            starter_version = await version_service.get_current_version(STARTER_PLAN, session)
            monthly_price = starter_version.price_for(MONTHLY_PERIOD)

            subscription = await subscription_service.get_client_subscription(client.id, session)
            subscription.plan_version_id = starter_version.id
            subscription.plan_version_price_id = monthly_price.id
            subscription.provider_subscription_id = f"sub_{uuid4().hex[:8]}"
            await session.commit()

        # Asking for the same plan family on a yearly cadence must be refused
        async with licensing_app_manager.database.get_session() as session:
            pro_version = await version_service.get_current_version(PRO_PLAN, session)

            result = await subscription_service.subscribe_to_plan(
                client_id=client.id,
                plan_version_id=pro_version.id,
                billing_period=YEARLY_PERIOD,
                success_url="https://example.com/success",
                webhook_url="https://example.com/webhooks/mollie",
                session=session
            )

            assert result.success is False
            assert result.error == BILLING_TERMS_CHANGE_ERROR


class TestChangePlanKeepsPriceCoherent:
    """An immediate plan change must not leave a price from another version."""

    @pytest.mark.asyncio
    async def test_immediate_change_realigns_the_price(self, licensing_app_manager):
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Realign-Corp-{uuid4().hex[:8]}",
                email=f"realign-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with licensing_app_manager.database.get_session() as session:
            starter = await version_service.get_current_version(STARTER_PLAN, session)
            subscription = await subscription_service.get_client_subscription(client.id, session)
            subscription.plan_version_id = starter.id
            subscription.plan_version_price_id = starter.price_for(MONTHLY_PERIOD).id
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            pro = await version_service.get_current_version(PRO_PLAN, session)

            subscription = await subscription_service.change_plan(
                client_id=client.id,
                new_plan_version_id=pro.id,
                session=session,
                immediate=True
            )

            assert subscription.plan_version_id == pro.id
            # The price now belongs to the plan actually subscribed to
            assert subscription.plan_version_price_id == pro.price_for(MONTHLY_PERIOD).id

    @pytest.mark.asyncio
    async def test_target_without_matching_price_raises(self, licensing_app_manager):
        subscription_service = licensing_app_manager.get_service("subscription")
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")
        client_service = licensing_app_manager.get_service("client")

        plan_id = f"YEARLY_ONLY_{uuid4().hex[:6]}"
        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Yearly-Corp-{uuid4().hex[:8]}",
                email=f"yearly-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            yearly_only = await version_service.create_new_version(
                plan_id, session,
                prices=[{"period_id": YEARLY_PERIOD, "amount": 30000}],
                rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
            )

            starter = await version_service.get_current_version(STARTER_PLAN, session)
            subscription = await subscription_service.get_client_subscription(client.id, session)
            subscription.plan_version_id = starter.id
            subscription.plan_version_price_id = starter.price_for(MONTHLY_PERIOD).id
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            with pytest.raises(LysError, match="PLAN_VERSION_NOT_PRICED"):
                await subscription_service.change_plan(
                    client_id=client.id,
                    new_plan_version_id=yearly_only.id,
                    session=session,
                    immediate=True
                )


class TestCommitment:
    """A commitment binds the client until its term."""

    @staticmethod
    async def _committed_client(licensing_app_manager, months=36):
        """Put a client on a paid yearly plan committed for `months` months."""
        client_service = licensing_app_manager.get_service("client")
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")
        commitment_service = licensing_app_manager.get_service("license_commitment")
        subscription_service = licensing_app_manager.get_service("subscription")

        commitment_id = f"COMMIT_{months}M_{uuid4().hex[:6]}"
        plan_id = f"COMMITTED_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Commit-Corp-{uuid4().hex[:8]}",
                email=f"commit-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await commitment_service.create(
                session=session, id=commitment_id, enabled=True, duration_months=months
            )
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            version = await version_service.create_new_version(
                plan_id, session,
                prices=[{
                    "period_id": YEARLY_PERIOD,
                    "amount": 30000,
                    "commitment_id": commitment_id,
                }],
                rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
            )

            # The freshly created version has no loaded prices yet, so the price
            # is looked up on its own rather than through the relationship
            price_service = licensing_app_manager.get_service("license_plan_version_price")
            prices = await price_service.get_all(session)
            price = next(
                p for p in prices
                if p.plan_version_id == version.id and p.commitment_id == commitment_id
            )

            subscription = await subscription_service.get_client_subscription(client.id, session)
            subscription.plan_version_id = version.id
            subscription.plan_version_price_id = price.id
            subscription.provider_subscription_id = f"sub_{uuid4().hex[:8]}"
            subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=300)
            subscription.commitment_end_date = datetime.now(timezone.utc) + timedelta(days=900)
            client.provider_customer_id = f"cst_{uuid4().hex[:8]}"
            client_id = client.id
            version_id = version.id
            await session.commit()

        return client_id, version_id, commitment_id

    @pytest.mark.asyncio
    async def test_downgrade_is_deferred_to_the_term_while_committed(self, licensing_app_manager):
        """The commitment is honoured by deferring, not by refusing."""
        subscription_service = licensing_app_manager.get_service("subscription")
        version_service = licensing_app_manager.get_service("license_plan_version")

        client_id, _, commitment_id = await self._committed_client(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            free_version = await version_service.get_current_version(FREE_PLAN, session)
            subscription = await subscription_service.get_client_subscription(client_id, session)
            commitment_end = subscription.commitment_end_date

            result = await subscription_service.subscribe_to_plan(
                client_id=client_id,
                plan_version_id=free_version.id,
                billing_period=YEARLY_PERIOD,
                success_url="https://example.com/success",
                webhook_url="https://example.com/webhooks/mollie",
                session=session,
                commitment_id=commitment_id
            )

            assert result.success is True
            assert result.effective_date == commitment_end
            assert subscription.pending_plan_version_id == free_version.id
            # Collection continues until the term
            assert subscription.provider_subscription_id is not None

    @pytest.mark.asyncio
    async def test_cancel_defers_to_the_term_and_keeps_collecting(self, licensing_app_manager):
        """
        The provider subscription must stay alive: the client owes every period
        until the term. Stopping it now would hand out free months.
        """
        subscription_service = licensing_app_manager.get_service("subscription")

        client_id, _, _ = await self._committed_client(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)
            provider_id = subscription.provider_subscription_id
            commitment_end = subscription.commitment_end_date

            # The cancellation event is dispatched through Celery, out of scope here
            with patch(
                "lys.apps.licensing.modules.subscription.services.trigger_event.delay"
            ):
                result = await subscription_service.cancel(client_id, session)

            assert result.success is True
            # Effective at the commitment term, not at the end of the period
            assert result.effective_date == commitment_end
            # Collection continues until then
            assert subscription.provider_subscription_id == provider_id
            assert subscription.canceled_at is None
            assert subscription.pending_plan_version_id is not None

    @pytest.mark.asyncio
    async def test_expired_commitment_no_longer_binds(self, licensing_app_manager):
        subscription_service = licensing_app_manager.get_service("subscription")

        client_id, _, _ = await self._committed_client(licensing_app_manager)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)
            subscription.commitment_end_date = datetime.now(timezone.utc) - timedelta(days=1)
            await session.commit()

            assert subscription.is_committed is False
            assert subscription.effective_change_date == subscription.current_period_end


class TestCommitmentPriceValidation:
    """A commitment must span a whole number of billing periods."""

    @pytest.mark.asyncio
    async def test_commitment_not_divisible_by_period_is_refused(self, licensing_app_manager):
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")
        commitment_service = licensing_app_manager.get_service("license_commitment")

        plan_id = f"ODD_COMMIT_{uuid4().hex[:6]}"
        commitment_id = f"COMMIT_18M_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            await commitment_service.create(
                session=session, id=commitment_id, enabled=True, duration_months=18
            )
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )

            # 18 months of commitment cannot be split into whole years
            with pytest.raises(LysError, match="INVALID_COMMITMENT_DURATION"):
                await version_service.create_new_version(
                    plan_id, session,
                    prices=[{
                        "period_id": YEARLY_PERIOD,
                        "amount": 30000,
                        "commitment_id": commitment_id,
                    }],
                    rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
                )


class TestNoticePeriodAndTacitRenewal:
    """Past the notice deadline the commitment renews and denunciation is refused."""

    @staticmethod
    async def _client_with_notice(licensing_app_manager, notice_months, days_to_term):
        """Commit a client with a notice period, whose term is `days_to_term` away."""
        client_service = licensing_app_manager.get_service("client")
        plan_service = licensing_app_manager.get_service("license_plan")
        version_service = licensing_app_manager.get_service("license_plan_version")
        commitment_service = licensing_app_manager.get_service("license_commitment")
        price_service = licensing_app_manager.get_service("license_plan_version_price")
        subscription_service = licensing_app_manager.get_service("subscription")

        commitment_id = f"NOTICE_{uuid4().hex[:6]}"
        plan_id = f"NOTICE_PLAN_{uuid4().hex[:6]}"

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Notice-Corp-{uuid4().hex[:8]}",
                email=f"notice-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await commitment_service.create(
                session=session, id=commitment_id, enabled=True,
                duration_months=36, renewal_months=12, notice_months=notice_months
            )
            await plan_service.create(
                session=session, id=plan_id, enabled=True, app_id=DEFAULT_APPLICATION
            )
            version = await version_service.create_new_version(
                plan_id, session,
                prices=[{
                    "period_id": YEARLY_PERIOD,
                    "amount": 30000,
                    "commitment_id": commitment_id,
                }],
                rules=[{"rule_id": MAX_USERS, "limit_value": 10}]
            )
            prices = await price_service.get_all(session)
            price = next(p for p in prices if p.plan_version_id == version.id)

            subscription = await subscription_service.get_client_subscription(client.id, session)
            subscription.plan_version_id = version.id
            subscription.plan_version_price_id = price.id
            subscription.provider_subscription_id = f"sub_{uuid4().hex[:8]}"
            subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
            subscription.commitment_end_date = (
                datetime.now(timezone.utc) + timedelta(days=days_to_term)
            )
            client.provider_customer_id = f"cst_{uuid4().hex[:8]}"
            client_id = client.id
            await session.commit()

        return client_id

    @pytest.mark.asyncio
    async def test_denunciation_inside_the_notice_window_is_accepted(self, licensing_app_manager):
        subscription_service = licensing_app_manager.get_service("subscription")

        # Term in 300 days, 3 months of notice: the deadline is far ahead
        client_id = await self._client_with_notice(licensing_app_manager, 3, 300)

        async with licensing_app_manager.database.get_session() as session:
            with patch(
                "lys.apps.licensing.modules.subscription.services.trigger_event.delay"
            ):
                result = await subscription_service.cancel(client_id, session)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_denunciation_past_the_deadline_is_refused(self, licensing_app_manager):
        subscription_service = licensing_app_manager.get_service("subscription")

        # Term in 30 days with 3 months of notice: the deadline has passed
        client_id = await self._client_with_notice(licensing_app_manager, 3, 30)

        async with licensing_app_manager.database.get_session() as session:
            result = await subscription_service.cancel(client_id, session)

            assert result.success is False
            assert result.error == NOTICE_PERIOD_EXPIRED_ERROR

            subscription = await subscription_service.get_client_subscription(client_id, session)
            assert subscription.pending_plan_version_id is None

    @pytest.mark.asyncio
    async def test_commitment_is_renewed_for_its_renewal_span(self, licensing_app_manager):
        """A term reached undenounced renews for renewal_months, not the initial duration."""
        from lys.apps.licensing.tasks import _renew_commitment

        subscription_service = licensing_app_manager.get_service("subscription")

        client_id = await self._client_with_notice(licensing_app_manager, 3, 1)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)
            term = subscription.commitment_end_date

            renewed = _renew_commitment(subscription)

            assert renewed == 1
            # Renewed by 12 months, not by the initial 36
            assert subscription.commitment_end_date.year == term.year + 1
            assert subscription.commitment_end_date.month == term.month

    @pytest.mark.asyncio
    async def test_commitment_without_renewal_span_simply_ends(self, licensing_app_manager):
        from lys.apps.licensing.tasks import _renew_commitment

        subscription_service = licensing_app_manager.get_service("subscription")
        commitment_service = licensing_app_manager.get_service("license_commitment")

        client_id = await self._client_with_notice(licensing_app_manager, 0, 1)

        async with licensing_app_manager.database.get_session() as session:
            subscription = await subscription_service.get_client_subscription(client_id, session)
            commitment = subscription.plan_version_price.commitment
            commitment.renewal_months = 0
            await session.flush()

            renewed = _renew_commitment(subscription)

            assert renewed == 0
            assert subscription.commitment_end_date is None
            assert subscription.is_committed is False
