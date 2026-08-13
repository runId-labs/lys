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
    BILLING_TERMS_CHANGE_ERROR,
    CANCEL_SUBSCRIPTION_FAILED_ERROR,
    CHECKOUT_SESSION_FAILED_ERROR,
    DEFAULT_CURRENCY,
    FREE_PLAN,
    NO_ACTIVE_SUBSCRIPTION_ERROR,
    NO_PROVIDER_SUBSCRIPTION_ERROR,
    PLAN_NOT_FOUND_ERROR,
    PLAN_NOT_PRICED_ERROR,
    SAME_PLAN_ERROR,
)
from lys.apps.licensing.errors import (
    NO_ACTIVE_SUBSCRIPTION,
    PLAN_VERSION_NOT_FOUND,
    PLAN_VERSION_NOT_PRICED,
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

        Administrative change: it does not talk to the payment provider. An
        immediate change realigns the subscribed price on the new version, using
        the periodicity and currency already subscribed to, so that the plan and
        the price recorded always belong to the same version. A deferred change
        leaves the price alone; it is resolved when apply_pending_plan_changes
        runs.

        Args:
            client_id: Client ID
            new_plan_version_id: New plan version to switch to
            session: Database session
            immediate: If True, change immediately. If False, schedule for period end.

        Returns:
            Updated Subscription entity

        Raises:
            LysError: If client has no subscription, the plan version does not
                exist, or the target version is paid but carries no price on the
                terms currently subscribed to
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
            current_price = subscription.plan_version_price
            new_price = None

            if current_price is not None:
                new_price = new_version.price_for(
                    current_price.period_id, current_price.currency_id
                )
                if new_price is None and not new_version.is_free:
                    raise LysError(
                        PLAN_VERSION_NOT_PRICED,
                        f"Plan version {new_plan_version_id} has no price for "
                        f"{current_price.period_id}/{current_price.currency_id}"
                    )

            subscription.plan_version_id = new_plan_version_id
            subscription.pending_plan_version_id = None
            subscription.plan_version_price_id = new_price.id if new_price else None
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
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY
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
            billing_period: Price period ID (e.g., "MONTHLY")
            success_url: URL to redirect after payment
            webhook_url: URL for payment provider webhooks
            session: Database session
            currency_id: Currency the subscription is billed in

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

        # Determine new plan price. A paid version that carries no price for the
        # requested terms must be rejected here: leaving it at 0 would make both
        # sides of the comparison below equal, route the request to the downgrade
        # branch, and schedule the plan change without any payment.
        new_price_entity = new_version.price_for(billing_period, currency_id)
        if new_price_entity is None and not new_version.is_free:
            logger.warning(
                f"Client {client_id} requested plan version {plan_version_id} "
                f"for {billing_period}/{currency_id}, which is not priced"
            )
            return SubscribeToPlanResult(success=False, error=PLAN_NOT_PRICED_ERROR)

        new_price = new_price_entity.amount if new_price_entity else 0

        # Case 1: No subscription or FREE plan (no provider_subscription_id)
        if not subscription or not subscription.provider_subscription_id:
            return await cls._handle_new_subscription(
                client=client,
                plan_version_id=plan_version_id,
                billing_period=billing_period,
                success_url=success_url,
                webhook_url=webhook_url,
                session=session,
                currency_id=currency_id
            )

        # Changing the periodicity or the currency of a running subscription is
        # not supported: the prorata below compares two amounts assumed to be on
        # the same cadence, so mixing a monthly and a yearly price would bill a
        # meaningless amount. Refuse rather than charge something wrong.
        current_terms = subscription.plan_version_price
        if current_terms is not None and (
            current_terms.period_id != billing_period
            or current_terms.currency_id != currency_id
        ):
            return SubscribeToPlanResult(success=False, error=BILLING_TERMS_CHANGE_ERROR)

        # Get current plan version and price
        current_version = await session.get(plan_version_entity, subscription.plan_version_id)
        current_price_entity = current_version.price_for(billing_period, currency_id)
        current_price = current_price_entity.amount if current_price_entity else 0

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
                session=session,
                currency_id=currency_id
            )

        # Case 4: Downgrade
        return await cls._handle_downgrade(
            subscription=subscription,
            plan_version_id=plan_version_id,
            session=session
        )

    @classmethod
    async def _handle_new_subscription(
        cls,
        client,
        plan_version_id: str,
        billing_period: str,
        success_url: str,
        webhook_url: str,
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY
    ) -> SubscribeToPlanResult:
        """Handle new subscription or upgrade from FREE plan."""
        checkout_service = cls.app_manager.get_service("mollie_checkout")
        checkout_url = await checkout_service.create_payment(
            client_id=client.id,
            plan_version_id=plan_version_id,
            billing_period=billing_period,
            redirect_url=success_url,
            webhook_url=webhook_url,
            session=session,
            currency_id=currency_id
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
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY
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
                session=session,
                currency_id=currency_id
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
            new_price_entity = new_version.price_for(billing_period, currency_id)

            subscription.plan_version_id = new_version.id
            subscription.pending_plan_version_id = None
            subscription.plan_version_price_id = new_price_entity.id

            # No payment is made here, so nothing else would align the recurring
            # collection with the plan now granted
            if subscription.provider_subscription_id and client.provider_customer_id:
                checkout_service = cls.app_manager.get_service("mollie_checkout")
                checkout_service.update_subscription_amount(
                    customer_id=client.provider_customer_id,
                    provider_subscription_id=subscription.provider_subscription_id,
                    currency_id=new_price_entity.currency_id,
                    value=new_price_entity.major_unit_value,
                    interval_months=new_price_entity.period.interval_months
                )

            return SubscribeToPlanResult(success=True, prorata_amount=0)

        # Create prorata payment
        mollie = get_mollie_client()
        if not mollie:
            return SubscribeToPlanResult(success=False, error=CHECKOUT_SESSION_FAILED_ERROR)

        currency = await cls.app_manager.get_service("license_currency").get_by_id(
            currency_id, session
        )

        try:
            payment_data = {
                "amount": {
                    "currency": currency_id,
                    "value": f"{currency.to_major_unit(prorata_amount):.{currency.minor_unit}f}"
                },
                "description": f"Upgrade to {new_version.plan_id} (prorata)",
                "redirectUrl": success_url,
                "webhookUrl": webhook_url,
                "metadata": {
                    "client_id": client.id,
                    "plan_version_id": new_version.id,
                    "billing_period": billing_period,
                    "currency_id": currency_id,
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
    async def _handle_downgrade(
        cls,
        subscription,
        plan_version_id: str,
        session: AsyncSession
    ) -> SubscribeToPlanResult:
        """
        Schedule a downgrade for the end of the current period.

        The client keeps the plan already paid for until the period ends, so the
        provider subscription is only touched when the target plan is free: in
        that case collection must stop, and nothing else would stop it.

        For a cheaper paid plan the amount is realigned when the change is
        applied, by apply_pending_plan_changes, since until then the client is
        still on the current plan and owes its price.

        Args:
            subscription: The subscription to downgrade
            plan_version_id: Target plan version
            session: Database session

        Returns:
            SubscribeToPlanResult with the effective date
        """
        subscription.pending_plan_version_id = plan_version_id

        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        target_version = await session.get(plan_version_entity, plan_version_id)

        if target_version is not None and target_version.is_free and subscription.provider_subscription_id:
            client_entity = cls.app_manager.get_entity("client")
            client = await session.get(client_entity, subscription.client_id)

            if client and client.provider_customer_id:
                checkout_service = cls.app_manager.get_service("mollie_checkout")
                canceled = checkout_service.cancel_provider_subscription(
                    customer_id=client.provider_customer_id,
                    provider_subscription_id=subscription.provider_subscription_id
                )
                if canceled:
                    subscription.canceled_at = datetime.now(timezone.utc)
                else:
                    logger.error(
                        f"Downgrade to a free plan for subscription {subscription.id} could not "
                        f"stop the provider subscription; the client would keep being charged"
                    )

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

        if not client.provider_customer_id:
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # Get FREE plan version to downgrade to
        plan_version_service = cls.app_manager.get_service("license_plan_version")
        free_version = await plan_version_service.get_current_version(FREE_PLAN, session)
        if not free_version:
            logger.error(f"No enabled version on the {FREE_PLAN} plan, cannot cancel")
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # A cancellation is a downgrade to the free plan: same scheduling, same
        # handling of the provider subscription
        await cls._handle_downgrade(
            subscription=subscription,
            plan_version_id=free_version.id,
            session=session
        )

        if subscription.canceled_at is None:
            # The provider subscription could not be stopped, so the client would
            # keep being charged; report the failure rather than a false success
            return CancelSubscriptionResult(success=False, error=CANCEL_SUBSCRIPTION_FAILED_ERROR)

        # Trigger subscription canceled event (notification + email)
        client_name = client.name if client else None
        plan_name = None
        if subscription.plan_version and subscription.plan_version.plan:
            plan_name = subscription.plan_version.plan.id
        effective_date = (
            subscription.current_period_end.isoformat()
            if subscription.current_period_end else None
        )

        trigger_event.delay(
            event_type=SUBSCRIPTION_CANCELED,
            user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
            email_context={
                "client_name": client_name,
                "plan_name": plan_name,
                "effective_date": effective_date,
                "front_url": cls.app_manager.settings.front_url,
            },
            notification_data={
                "client_name": client_name,
                "plan_name": plan_name,
                "effective_date": effective_date,
            },
            organization_data={"client_ids": [client_id]},
        )

        return CancelSubscriptionResult(
            success=True,
            effective_date=subscription.current_period_end
        )