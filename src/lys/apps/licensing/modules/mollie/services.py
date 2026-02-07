"""
Mollie services for licensing module.

Provides:
- MollieWebhookService: Handle Mollie webhook events
- MollieCheckoutService: Create checkout sessions

Configuration via plugins:
    settings.configure_plugin("payment",
        provider="mollie",
        api_key="live_xxx",
        webhook_secret="xxx"  # optional
    )
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from mollie.api.client import Client as MollieClient
from mollie.api.error import Error as MollieError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.modules.event.consts import (
    SUBSCRIPTION_PAYMENT_SUCCESS,
    SUBSCRIPTION_PAYMENT_FAILED,
    SUBSCRIPTION_CANCELED,
)
from lys.apps.licensing.modules.subscription.prorata import calculate_period_end
from lys.apps.user_auth.modules.event.tasks import trigger_event
from lys.core.configs import settings
from lys.core.registries import register_service
from lys.core.services import Service

logger = logging.getLogger(__name__)


def get_payment_config() -> Dict[str, Any]:
    """
    Get payment provider configuration from plugins.

    Returns:
        Payment config dict with keys: provider, api_key, webhook_secret
    """
    return settings.get_plugin_config("payment")


def is_payment_configured() -> bool:
    """Check if payment provider is configured."""
    config = get_payment_config()
    return bool(config.get("provider") and config.get("api_key"))


def get_payment_provider() -> Optional[str]:
    """Get configured payment provider name."""
    return get_payment_config().get("provider")


def get_webhook_base_url() -> Optional[str]:
    """Get webhook base URL override from config (for ngrok/tunnels)."""
    return get_payment_config().get("webhook_base_url")


def get_mollie_client() -> Optional[MollieClient]:
    """
    Get configured Mollie client.

    Returns:
        Mollie client or None if not configured or not Mollie
    """
    config = get_payment_config()

    if config.get("provider") != "mollie":
        return None

    api_key = config.get("api_key")
    if not api_key:
        return None

    client = MollieClient()
    client.set_api_key(api_key)
    return client


@register_service()
class MollieWebhookService(Service):
    """
    Service for handling Mollie webhook events.

    Processes payment and subscription notifications.
    """

    service_name = "mollie_webhook"

    # Payment status mapping
    PAYMENT_HANDLERS = {
        "paid": "_handle_payment_paid",
        "failed": "_handle_payment_failed",
        "expired": "_handle_payment_expired",
        "canceled": "_handle_payment_canceled",
    }

    # Subscription status mapping
    SUBSCRIPTION_HANDLERS = {
        "active": "_handle_subscription_active",
        "pending": "_handle_subscription_pending",
        "canceled": "_handle_subscription_canceled",
        "suspended": "_handle_subscription_suspended",
        "completed": "_handle_subscription_completed",
    }

    @classmethod
    async def handle_webhook(
        cls,
        resource_type: str,
        resource: Any,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Main entry point for processing Mollie webhooks.

        Args:
            resource_type: "payment", "subscription", or "order"
            resource: Mollie resource object (already fetched)
            session: Database session

        Returns:
            Dict with processing result
        """
        if resource_type == "payment":
            return await cls._handle_payment(resource, session)
        elif resource_type == "subscription":
            return await cls._handle_subscription(resource, session)
        else:
            logger.debug(f"Unhandled Mollie resource type: {resource_type}")
            return {"handled": False, "message": f"Resource type {resource_type} not handled"}

    @classmethod
    async def _handle_payment(cls, payment: Any, session: AsyncSession) -> Dict[str, Any]:
        """Handle payment webhook."""
        status = payment.status
        handler_name = cls.PAYMENT_HANDLERS.get(status)

        if not handler_name:
            logger.debug(f"Unhandled payment status: {status}")
            return {"handled": False, "message": f"Payment status {status} not handled"}

        handler = getattr(cls, handler_name)
        await handler(payment, session)

        logger.info(f"Processed Mollie payment {payment.id} with status {status}")
        return {"handled": True, "message": f"Payment {status} processed"}

    @classmethod
    async def _handle_subscription(cls, subscription: Any, session: AsyncSession) -> Dict[str, Any]:
        """Handle subscription webhook."""
        status = subscription.status
        handler_name = cls.SUBSCRIPTION_HANDLERS.get(status)

        if not handler_name:
            logger.debug(f"Unhandled subscription status: {status}")
            return {"handled": False, "message": f"Subscription status {status} not handled"}

        handler = getattr(cls, handler_name)
        await handler(subscription, session)

        logger.info(f"Processed Mollie subscription {subscription.id} with status {status}")
        return {"handled": True, "message": f"Subscription {status} processed"}

    # =========================================================================
    # Payment Handlers
    # =========================================================================

    @classmethod
    async def _handle_payment_paid(cls, payment: Any, session: AsyncSession) -> None:
        """
        Handle successful payment.

        For subscription payments:
        - First payment: Create Mollie subscription + activate in DB
        - Recurring payment: Update billing period dates
        """
        metadata = payment.metadata or {}
        client_id = metadata.get("client_id")
        plan_version_id = metadata.get("plan_version_id")
        billing_period = metadata.get("billing_period", "monthly")

        if not client_id:
            logger.warning(f"Payment {payment.id} missing client_id in metadata")
            return

        subscription_entity = cls.app_manager.get_entity("subscription")
        client_entity = cls.app_manager.get_entity("client")

        # Get subscription for this client
        stmt = select(subscription_entity).where(
            subscription_entity.client_id == client_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not plan_version_id:
            # CRITICAL: Payment received but no plan_version_id - this should never happen
            logger.critical(
                f"Payment {payment.id} for client {client_id} succeeded but missing plan_version_id. "
                f"Manual intervention required to assign plan or refund."
            )
            return

        # Calculate billing period dates
        now = datetime.now(timezone.utc)
        period_start = now
        period_end = calculate_period_end(now, billing_period)

        # Update client's provider customer ID first
        client = None
        if payment.customer_id:
            stmt = select(client_entity).where(client_entity.id == client_id)
            result = await session.execute(stmt)
            client = result.scalar_one_or_none()

            if client and not client.provider_customer_id:
                client.provider_customer_id = payment.customer_id

        if subscription:
            # Existing subscription - update plan version and billing dates
            if subscription.plan_version_id != plan_version_id:
                subscription.plan_version_id = plan_version_id
                subscription.pending_plan_version_id = None
                logger.info(f"Updated subscription {subscription.id} to plan version {plan_version_id}")

            # Update billing period tracking
            subscription.billing_period = billing_period
            subscription.current_period_start = period_start
            subscription.current_period_end = period_end

            # Update provider subscription ID if needed
            if payment.subscription_id and not subscription.provider_subscription_id:
                subscription.provider_subscription_id = payment.subscription_id
        else:
            # New subscription
            subscription = subscription_entity(
                client_id=client_id,
                plan_version_id=plan_version_id,
                provider_subscription_id=payment.subscription_id,
                billing_period=billing_period,
                current_period_start=period_start,
                current_period_end=period_end
            )
            session.add(subscription)
            logger.info(f"Created new subscription for client {client_id}")

        # For first payments (sequenceType == "first"), create Mollie subscription
        # This sets up recurring billing
        sequence_type = getattr(payment, "sequence_type", None)
        if sequence_type == "first" and payment.customer_id and not subscription.provider_subscription_id:
            # Build webhook URL from config
            webhook_base = get_webhook_base_url()
            if webhook_base:
                webhook_url = f"{webhook_base}/webhooks/mollie"

                checkout_service = cls.app_manager.get_service("mollie_checkout")
                mollie_sub_id = await checkout_service.create_subscription(
                    customer_id=payment.customer_id,
                    plan_version_id=plan_version_id,
                    billing_period=billing_period,
                    webhook_url=webhook_url,
                    session=session
                )

                if mollie_sub_id:
                    subscription.provider_subscription_id = mollie_sub_id
                    logger.info(f"Created Mollie subscription {mollie_sub_id} for client {client_id}")
                else:
                    logger.error(f"Failed to create Mollie subscription for client {client_id}")
            else:
                logger.warning(
                    f"Cannot create Mollie subscription for {client_id}: webhook_base_url not configured"
                )

        # Trigger payment success event (notification + email)
        trigger_event.delay(
            event_type=SUBSCRIPTION_PAYMENT_SUCCESS,
            user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
            notification_data={
                "plan_version_id": plan_version_id,
                "billing_period": billing_period,
                "amount": str(payment.amount["value"]) if hasattr(payment, "amount") else None,
                "currency": payment.amount["currency"] if hasattr(payment, "amount") else None,
            },
            organization_data={"client_ids": [client_id]},
        )

    @classmethod
    async def _handle_payment_failed(cls, payment: Any, session: AsyncSession) -> None:
        """Handle failed payment - trigger event."""
        metadata = payment.metadata or {}
        client_id = metadata.get("client_id")
        plan_version_id = metadata.get("plan_version_id")
        billing_period = metadata.get("billing_period")
        logger.warning(f"Payment failed for client {client_id}: {payment.id}")

        if client_id:
            # Trigger payment failed event (notification + email)
            trigger_event.delay(
                event_type=SUBSCRIPTION_PAYMENT_FAILED,
                user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
                notification_data={
                    "plan_version_id": plan_version_id,
                    "billing_period": billing_period,
                    "amount": str(payment.amount["value"]) if hasattr(payment, "amount") else None,
                    "currency": payment.amount["currency"] if hasattr(payment, "amount") else None,
                    "failure_reason": getattr(payment, "details", {}).get("failureReason") if hasattr(payment, "details") else None,
                },
                organization_data={"client_ids": [client_id]},
            )

    @classmethod
    async def _handle_payment_expired(cls, payment: Any, session: AsyncSession) -> None:
        """Handle expired payment."""
        metadata = payment.metadata or {}
        client_id = metadata.get("client_id")
        logger.warning(f"Payment expired for client {client_id}: {payment.id}")

    @classmethod
    async def _handle_payment_canceled(cls, payment: Any, session: AsyncSession) -> None:
        """Handle canceled payment."""
        metadata = payment.metadata or {}
        client_id = metadata.get("client_id")
        logger.info(f"Payment canceled for client {client_id}: {payment.id}")

    # =========================================================================
    # Subscription Handlers
    # =========================================================================

    @classmethod
    async def _handle_subscription_active(cls, mollie_sub: Any, session: AsyncSession) -> None:
        """Handle subscription becoming active."""
        logger.info(f"Subscription {mollie_sub.id} is now active")

    @classmethod
    async def _handle_subscription_pending(cls, mollie_sub: Any, session: AsyncSession) -> None:
        """Handle subscription pending (waiting for first payment)."""
        logger.info(f"Subscription {mollie_sub.id} is pending")

    @classmethod
    async def _handle_subscription_canceled(cls, mollie_sub: Any, session: AsyncSession) -> None:
        """
        Handle subscription cancellation.

        Downgrade client to FREE plan.
        """
        subscription_entity = cls.app_manager.get_entity("subscription")

        # Find subscription by provider ID
        stmt = select(subscription_entity).where(
            subscription_entity.provider_subscription_id == mollie_sub.id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(f"Subscription not found for Mollie ID {mollie_sub.id}")
            return

        # Get FREE plan version
        plan_service = cls.app_manager.get_service("license_plan")
        plan_version_service = cls.app_manager.get_service("license_plan_version")

        free_plan = await plan_service.get_by_id("FREE", session)
        if free_plan:
            free_version = await plan_version_service.get_current_version(free_plan.id, session)
            if free_version:
                subscription.plan_version_id = free_version.id
                subscription.provider_subscription_id = None
                subscription.pending_plan_version_id = None
                logger.info(f"Downgraded subscription {subscription.id} to FREE plan")

    @classmethod
    async def _handle_subscription_suspended(cls, mollie_sub: Any, session: AsyncSession) -> None:
        """Handle subscription suspension (payment issues)."""
        logger.warning(f"Subscription {mollie_sub.id} suspended")

    @classmethod
    async def _handle_subscription_completed(cls, mollie_sub: Any, session: AsyncSession) -> None:
        """Handle subscription completion (fixed-term ended)."""
        logger.info(f"Subscription {mollie_sub.id} completed")


@register_service()
class MollieCheckoutService(Service):
    """
    Service for creating Mollie checkout sessions.
    """

    service_name = "mollie_checkout"

    @classmethod
    async def create_payment(
        cls,
        client_id: str,
        plan_version_id: str,
        billing_period: str,
        redirect_url: str,
        webhook_url: str,
        session: AsyncSession,
        cancel_url: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a Mollie payment for subscription.

        Args:
            client_id: Client ID
            plan_version_id: Plan version to subscribe to
            billing_period: "monthly" or "yearly"
            redirect_url: URL to redirect after payment (success/pending/failed)
            webhook_url: URL for Mollie webhooks
            session: Database session
            cancel_url: URL to redirect if user cancels (optional)

        Returns:
            Checkout URL or None on failure
        """
        mollie = get_mollie_client()
        if not mollie:
            logger.error("Mollie not configured")
            return None

        # Get plan version for pricing
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        version = await session.get(plan_version_entity, plan_version_id)

        if not version:
            logger.error(f"Plan version {plan_version_id} not found")
            return None

        # Get price based on billing period
        if billing_period == "yearly":
            amount = version.price_yearly
        else:
            amount = version.price_monthly

        if not amount:
            logger.error(f"No price for {billing_period} billing")
            return None

        # Get or create Mollie customer
        client_entity = cls.app_manager.get_entity("client")
        client = await session.get(client_entity, client_id)

        customer_id = None
        if client:
            if client.provider_customer_id:
                customer_id = client.provider_customer_id
            else:
                # Create Mollie customer
                try:
                    customer = mollie.customers.create({
                        "name": client.name if hasattr(client, "name") else f"Client {client_id}",
                        "metadata": {"client_id": client_id}
                    })
                    client.provider_customer_id = customer.id
                    customer_id = customer.id
                except MollieError as e:
                    logger.error(f"Error creating Mollie customer: {e}")

        # Create payment
        try:
            payment_data = {
                "amount": {
                    "currency": version.currency.upper(),
                    "value": f"{amount / 100:.2f}"
                },
                "description": f"{version.plan_id} - {billing_period}",
                "redirectUrl": redirect_url,
                "webhookUrl": webhook_url,
                "metadata": {
                    "client_id": client_id,
                    "plan_version_id": plan_version_id,
                    "billing_period": billing_period
                }
            }

            if customer_id:
                payment_data["customerId"] = customer_id
                payment_data["sequenceType"] = "first"

            payment = mollie.payments.create(payment_data)

            return payment.checkout_url

        except MollieError as e:
            logger.error(f"Error creating Mollie payment: {e}")
            return None

    @classmethod
    async def create_subscription(
        cls,
        customer_id: str,
        plan_version_id: str,
        billing_period: str,
        webhook_url: str,
        session: AsyncSession
    ) -> Optional[str]:
        """
        Create a recurring Mollie subscription.

        Called after first payment is successful and mandate is created.

        Returns:
            Mollie subscription ID or None on failure
        """
        mollie = get_mollie_client()
        if not mollie:
            return None

        # Get plan version for pricing
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        version = await session.get(plan_version_entity, plan_version_id)

        if not version:
            return None

        if billing_period == "yearly":
            amount = version.price_yearly
            interval = "12 months"
        else:
            amount = version.price_monthly
            interval = "1 month"

        if not amount:
            return None

        try:
            customer = mollie.customers.get(customer_id)
            subscription = customer.subscriptions.create(data={
                "amount": {
                    "currency": version.currency.upper(),
                    "value": f"{amount / 100:.2f}"
                },
                "interval": interval,
                "description": f"{version.plan_id} subscription",
                "webhookUrl": webhook_url,
                "metadata": {
                    "plan_version_id": plan_version_id
                }
            })

            return subscription.id

        except MollieError as e:
            logger.error(f"Error creating Mollie subscription: {e}")
            return None
