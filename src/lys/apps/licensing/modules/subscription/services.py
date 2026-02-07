"""
Subscription services.

This module provides:
- SubscriptionService: Core subscription management
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import (
    CANCEL_SUBSCRIPTION_FAILED_ERROR,
    CHECKOUT_SESSION_FAILED_ERROR,
    FREE_PLAN,
    NO_ACTIVE_SUBSCRIPTION_ERROR,
    NO_PROVIDER_SUBSCRIPTION_ERROR,
    PLAN_NOT_FOUND_ERROR,
    SAME_PLAN_ERROR,
)
from lys.apps.licensing.errors import (
    NO_ACTIVE_SUBSCRIPTION,
    PLAN_VERSION_NOT_FOUND,
    SUBSCRIPTION_ALREADY_EXISTS,
    USER_ALREADY_LICENSED,
    USER_NOT_LICENSED,
)
from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_CANCELED
from lys.apps.user_auth.modules.event.tasks import trigger_event
from lys.apps.licensing.modules.mollie.models import (
    CancelSubscriptionResult,
    SubscribeToPlanResult,
)
from lys.apps.licensing.modules.mollie.services import get_mollie_client
from lys.apps.licensing.modules.subscription.entities import Subscription, subscription_user
from lys.apps.licensing.modules.subscription.prorata import (
    calculate_prorata,
    is_upgrade,
)
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService

logger = logging.getLogger(__name__)


@register_service()
class SubscriptionService(EntityService[Subscription]):
    """
    Service for managing client subscriptions.

    Each client has at most one active subscription at a time.
    Subscriptions link clients to plan versions.
    """

    @classmethod
    async def get_client_subscription(
        cls,
        client_id: str,
        session: AsyncSession
    ) -> Subscription | None:
        """
        Get the active subscription for a client.

        Args:
            client_id: Client ID
            session: Database session

        Returns:
            Subscription entity or None if no active subscription
        """
        stmt = select(cls.entity_class).where(
            cls.entity_class.client_id == client_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def create_subscription(
        cls,
        client_id: str,
        plan_version_id: str,
        session: AsyncSession,
        provider_subscription_id: str | None = None
    ) -> Subscription:
        """
        Create a new subscription for a client.

        Args:
            client_id: Client ID
            plan_version_id: Plan version to subscribe to
            session: Database session
            provider_subscription_id: Optional payment provider subscription ID

        Returns:
            New Subscription entity

        Raises:
            LysError: If client already has a subscription
        """
        # Check if client already has a subscription
        existing = await cls.get_client_subscription(client_id, session)
        if existing:
            raise LysError(
                SUBSCRIPTION_ALREADY_EXISTS,
                f"Client {client_id} already has an active subscription"
            )

        # Verify plan version exists
        plan_version_service = cls.app_manager.get_service("license_plan_version")
        plan_version = await plan_version_service.get_by_id(plan_version_id, session)
        if not plan_version:
            raise LysError(
                PLAN_VERSION_NOT_FOUND,
                f"Plan version {plan_version_id} not found"
            )

        return await cls.create(
            session,
            client_id=client_id,
            plan_version_id=plan_version_id,
            provider_subscription_id=provider_subscription_id
        )

    @classmethod
    async def change_plan(
        cls,
        client_id: str,
        new_plan_version_id: str,
        session: AsyncSession,
        immediate: bool = True
    ) -> Subscription:
        """
        Change the subscription plan for a client.

        Args:
            client_id: Client ID
            new_plan_version_id: New plan version to switch to
            session: Database session
            immediate: If True, change immediately. If False, schedule for period end.

        Returns:
            Updated Subscription entity

        Raises:
            LysError: If client has no subscription or plan version not found
        """
        subscription = await cls.get_client_subscription(client_id, session)
        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_id} has no active subscription"
            )

        # Verify new plan version exists
        plan_version_service = cls.app_manager.get_service("license_plan_version")
        new_version = await plan_version_service.get_by_id(new_plan_version_id, session)
        if not new_version:
            raise LysError(
                PLAN_VERSION_NOT_FOUND,
                f"Plan version {new_plan_version_id} not found"
            )

        if immediate:
            subscription.plan_version_id = new_plan_version_id
            subscription.pending_plan_version_id = None
        else:
            # Schedule change for billing period end (downgrade)
            subscription.pending_plan_version_id = new_plan_version_id

        return subscription

    @classmethod
    async def apply_pending_change(
        cls,
        subscription_id: str,
        session: AsyncSession
    ) -> Subscription | None:
        """
        Apply a pending plan change (called at billing period end).

        Args:
            subscription_id: Subscription ID
            session: Database session

        Returns:
            Updated Subscription or None if no pending change
        """
        subscription = await cls.get_by_id(subscription_id, session)
        if not subscription or not subscription.pending_plan_version_id:
            return None

        subscription.plan_version_id = subscription.pending_plan_version_id
        subscription.pending_plan_version_id = None
        return subscription

    @classmethod
    async def is_user_in_subscription(
        cls,
        subscription_id: str,
        user_id: str,
        session: AsyncSession
    ) -> bool:
        """
        Check if a user is already in a subscription.

        Args:
            subscription_id: Subscription ID
            user_id: User ID
            session: Database session

        Returns:
            True if user is already in the subscription
        """
        stmt = select(subscription_user).where(
            subscription_user.c.subscription_id == subscription_id,
            subscription_user.c.user_id == user_id
        ).limit(1)
        result = await session.execute(stmt)
        return result.first() is not None

    @classmethod
    async def add_user_to_subscription(
        cls,
        subscription_id: str,
        user_id: str,
        session: AsyncSession
    ) -> None:
        """
        Add a user to a subscription (license seat).

        Args:
            subscription_id: Subscription ID
            user_id: User ID
            session: Database session

        Raises:
            LysError: If user is already in the subscription
        """
        # Check if user is already in the subscription
        if await cls.is_user_in_subscription(subscription_id, user_id, session):
            raise LysError(
                USER_ALREADY_LICENSED,
                f"User {user_id} is already in subscription {subscription_id}"
            )

        stmt = subscription_user.insert().values(
            subscription_id=subscription_id,
            user_id=user_id
        )
        await session.execute(stmt)

    @classmethod
    async def remove_user_from_subscription(
        cls,
        subscription_id: str,
        user_id: str,
        session: AsyncSession
    ) -> None:
        """
        Remove a user from a subscription.

        Args:
            subscription_id: Subscription ID
            user_id: User ID
            session: Database session

        Raises:
            LysError: If user is not in the subscription
        """
        # Check if user is in the subscription
        if not await cls.is_user_in_subscription(subscription_id, user_id, session):
            raise LysError(
                USER_NOT_LICENSED,
                f"User {user_id} is not in subscription {subscription_id}"
            )

        stmt = subscription_user.delete().where(
            subscription_user.c.subscription_id == subscription_id,
            subscription_user.c.user_id == user_id
        )
        await session.execute(stmt)

    @classmethod
    async def get_subscription_user_count(
        cls,
        subscription_id: str,
        session: AsyncSession
    ) -> int:
        """
        Get the number of users on a subscription.

        Args:
            subscription_id: Subscription ID
            session: Database session

        Returns:
            Number of users
        """
        stmt = select(func.count()).select_from(subscription_user).where(
            subscription_user.c.subscription_id == subscription_id
        )
        result = await session.execute(stmt)
        return result.scalar() or 0

    @classmethod
    async def is_user_licensed(
        cls,
        user_id: str,
        session: AsyncSession
    ) -> bool:
        """
        Check if a user has a license (is associated with any subscription).

        Args:
            user_id: User ID
            session: Database session

        Returns:
            True if user is associated with a subscription
        """
        stmt = select(subscription_user).where(
            subscription_user.c.user_id == user_id
        ).limit(1)
        result = await session.execute(stmt)
        return result.first() is not None

    # =========================================================================
    # Subscription Management (with payment provider integration)
    # =========================================================================

    @classmethod
    async def subscribe_to_plan(
        cls,
        client_id: str,
        plan_version_id: str,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession
    ) -> SubscribeToPlanResult:
        """
        Subscribe a client to a plan, handling all cases automatically.

        Cases handled:
        - No subscription or FREE plan: Create new paid subscription
        - Upgrade: Calculate prorata and create payment
        - Downgrade: Schedule change for end of billing period
        - Same plan: Return error

        Args:
            client_id: Client ID
            plan_version_id: Target plan version ID
            billing_period: "monthly" or "yearly"
            success_url: URL to redirect after payment
            webhook_url: URL for payment provider webhooks
            session: Database session

        Returns:
            SubscribeToPlanResult with checkout_url or effective_date
        """
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        client_entity = cls.app_manager.get_entity("client")

        # Get target plan version
        new_version = await session.get(plan_version_entity, plan_version_id)
        if not new_version:
            return SubscribeToPlanResult(success=False, error=PLAN_NOT_FOUND_ERROR)

        # Get client
        client = await session.get(client_entity, client_id)
        if not client:
            return SubscribeToPlanResult(success=False, error="CLIENT_NOT_FOUND")

        # Get current subscription
        subscription = await cls.get_client_subscription(client_id, session)

        # Determine new plan price
        if billing_period == "yearly":
            new_price = new_version.price_yearly or 0
        else:
            new_price = new_version.price_monthly or 0

        # Case 1: No subscription or FREE plan (no provider_subscription_id)
        if not subscription or not subscription.provider_subscription_id:
            return await cls._handle_new_subscription(
                client=client,
                plan_version_id=plan_version_id,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session
            )

        # Get current plan version and price
        current_version = await session.get(plan_version_entity, subscription.plan_version_id)
        if billing_period == "yearly":
            current_price = current_version.price_yearly or 0
        else:
            current_price = current_version.price_monthly or 0

        # Case 2: Same plan
        if subscription.plan_version_id == plan_version_id:
            return SubscribeToPlanResult(success=False, error=SAME_PLAN_ERROR)

        # Case 3: Upgrade
        if is_upgrade(current_price, new_price):
            return await cls._handle_upgrade(
                client=client,
                subscription=subscription,
                new_version=new_version,
                current_price=current_price,
                new_price=new_price,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session
            )

        # Case 4: Downgrade
        return cls._handle_downgrade(
            subscription=subscription,
            plan_version_id=plan_version_id
        )

    @classmethod
    async def _handle_new_subscription(
        cls,
        client,
        plan_version_id: str,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession
    ) -> SubscribeToPlanResult:
        """Handle new subscription or upgrade from FREE plan."""
        checkout_service = cls.app_manager.get_service("mollie_checkout")
        checkout_url = await checkout_service.create_payment(
            client_id=client.id,
            plan_version_id=plan_version_id,
            billing_period=billing_period,
            redirect_url=success_url,
            webhook_url=webhook_url,
            session=session
        )

        if not checkout_url:
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

        return SubscribeToPlanResult(success=True, checkout_url=checkout_url)

    @classmethod
    async def _handle_upgrade(
        cls,
        client,
        subscription,
        new_version,
        current_price: int,
        new_price: int,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession
    ) -> SubscribeToPlanResult:
        """Handle upgrade with prorata calculation."""
        # No billing period info - treat as new subscription
        if not subscription.current_period_start or not subscription.current_period_end:
            return await cls._handle_new_subscription(
                client=client,
                plan_version_id=new_version.id,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session
            )

        # Calculate prorata
        prorata_amount = calculate_prorata(
            old_price=current_price,
            new_price=new_price,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end
        )

        # No prorata needed (period almost over) - apply immediately
        if prorata_amount <= 0:
            subscription.plan_version_id = new_version.id
            subscription.pending_plan_version_id = None
            return SubscribeToPlanResult(success=True, prorata_amount=0)

        # Create prorata payment
        mollie = get_mollie_client()
        if not mollie:
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

        try:
            payment_data = {
                "amount": {
                    "currency": new_version.currency.upper(),
                    "value": f"{prorata_amount / 100:.2f}"
                },
                "description": f"Upgrade to {new_version.plan_id} (prorata)",
                "redirectUrl": success_url,
                "webhookUrl": webhook_url,
                "metadata": {
                    "client_id": client.id,
                    "plan_version_id": new_version.id,
                    "billing_period": billing_period,
                    "is_prorata": True
                }
            }

            if client.provider_customer_id:
                payment_data["customerId"] = client.provider_customer_id

            payment = mollie.payments.create(payment_data)

            return SubscribeToPlanResult(
                success=True,
                checkout_url=payment.checkout_url,
                prorata_amount=prorata_amount
            )

        except Exception as e:
            logger.error(f"Error creating prorata payment: {e}")
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

    @classmethod
    def _handle_downgrade(
        cls,
        subscription,
        plan_version_id: str
    ) -> SubscribeToPlanResult:
        """Handle downgrade - schedule for end of period."""
        subscription.pending_plan_version_id = plan_version_id
        return SubscribeToPlanResult(
            success=True,
            effective_date=subscription.current_period_end
        )

    @classmethod
    async def cancel(
        cls,
        client_id: str,
        session: AsyncSession
    ) -> CancelSubscriptionResult:
        """
        Cancel a subscription.

        The cancellation takes effect at the end of the current billing period.
        The client keeps access until then, then downgrades to FREE plan.

        Args:
            client_id: Client ID
            session: Database session

        Returns:
            CancelSubscriptionResult with effective_date
        """
        client_entity = cls.app_manager.get_entity("client")

        # Get client
        client = await session.get(client_entity, client_id)
        if not client:
            return CancelSubscriptionResult(success=False, error="CLIENT_NOT_FOUND")

        # Get subscription
        subscription = await cls.get_client_subscription(client_id, session)
        if not subscription:
            return CancelSubscriptionResult(success=False, error=NO_ACTIVE_SUBSCRIPTION_ERROR)

        if not subscription.provider_subscription_id:
            return CancelSubscriptionResult(success=False, error=NO_PROVIDER_SUBSCRIPTION_ERROR)

        # Cancel Mollie subscription
        mollie = get_mollie_client()
        if not mollie or not client.provider_customer_id:
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        try:
            customer = mollie.customers.get(client.provider_customer_id)
            customer.subscriptions.delete(subscription.provider_subscription_id)
        except Exception as e:
            logger.error(f"Error canceling Mollie subscription: {e}")
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # Mark subscription as canceled
        subscription.canceled_at = datetime.now(timezone.utc)

        # Get FREE plan version for scheduled downgrade
        plan_service = cls.app_manager.get_service("license_plan")
        plan_version_service = cls.app_manager.get_service("license_plan_version")

        free_plan = await plan_service.get_by_id(FREE_PLAN, session)
        if free_plan:
            free_version = await plan_version_service.get_current_version(free_plan.id, session)
            if free_version:
                subscription.pending_plan_version_id = free_version.id

        # Trigger subscription canceled event (notification + email)
        plan_name = None
        if subscription.plan_version and subscription.plan_version.plan:
            plan_name = subscription.plan_version.plan.name

        trigger_event.delay(
            event_type=SUBSCRIPTION_CANCELED,
            user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
            notification_data={
                "plan_name": plan_name,
                "effective_date": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            },
            organization_data={"client_ids": [client_id]},
        )

        return CancelSubscriptionResult(
            success=True,
            effective_date=subscription.current_period_end
        )