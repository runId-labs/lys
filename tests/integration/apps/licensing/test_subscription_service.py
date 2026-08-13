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
from uuid import uuid4

from lys.apps.licensing.consts import (
    BILLING_TERMS_CHANGE_ERROR,
    DEFAULT_APPLICATION,
    FREE_PLAN,
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
                plan_id, session, prices=[{"period_id": MONTHLY_PERIOD, "amount": 2500}]
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
                plan_id, session, prices=[{"period_id": YEARLY_PERIOD, "amount": 30000}]
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
