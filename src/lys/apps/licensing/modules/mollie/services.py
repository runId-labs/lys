"""
Mollie services for licensing module.

Provides:
- MollieWebhookService: Handle Mollie webhook events
- MollieCheckoutService: Create checkout sessions

Configuration via plugins:
    settings.configure_plugin("payment",
        provider="mollie",
        api_key="live_xxx",
    )
"""
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from mollie.api.client import Client as MollieClient
from mollie.api.error import Error as MollieError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.modules.discount.amounts import discounted_amount
from lys.apps.licensing.consts import (
    DEFAULT_CURRENCY,
    MANUAL_GRANT,
    MONTHLY_PERIOD,
    NO_COMMITMENT,
    PROVIDER_BILLING,
)
from lys.apps.licensing.modules.event.consts import (
    SUBSCRIPTION_PAYMENT_SUCCESS,
    SUBSCRIPTION_PAYMENT_FAILED,
    SUBSCRIPTION_CANCELED,
)
from lys.apps.licensing.modules.subscription.prorata import calculate_period_end
from lys.apps.user_auth.modules.event.tasks import trigger_event
from lys.core.configs import settings
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import Service

if TYPE_CHECKING:
    # Annotations only: entities and services are resolved through app_manager
    # at runtime, never imported.
    from lys.apps.licensing.modules.plan.entities import LicensePlanVersionPrice
    from lys.apps.licensing.modules.subscription.entities import Subscription
    from lys.apps.licensing.modules.subscription.services import SubscriptionService

logger = logging.getLogger(__name__)


def get_payment_config() -> Dict[str, Any]:
    """
    Get payment provider configuration from plugins.

    Returns:
        Payment config dict with keys: provider, api_key
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
    async def _grant_claimed_discount(
        cls,
        subscription_service: type["SubscriptionService"],
        subscription: "Subscription",
        discount_id: Optional[str],
        session: AsyncSession
    ) -> None:
        """Grant the discount claimed at checkout, once the payment is confirmed.

        Only the first payment carries it: Mollie forwards a subscription's
        metadata to every payment it generates, so declaring the discount there
        would grant it again at each renewal, including after the commitment it
        was granted against had ended.

        Silent when there is nothing to grant or a discount is already in place:
        a webhook can be delivered more than once, and a payment confirmation is
        no place to fail over a commercial detail — the refusal is logged
        instead, so that a missed grant is traceable.

        Only a refusal is caught. A database error is left to propagate: the
        session is then unusable, and swallowing it would let the rest of the
        confirmation run on a broken transaction.
        """
        if not discount_id:
            return

        if await subscription_service.get_granted_discount(subscription, session) is not None:
            return

        try:
            await subscription_service.grant_discount(
                subscription, discount_id, session, claimed=True
            )
        except LysError as e:
            logger.error(
                f"Could not grant discount {discount_id} claimed at checkout for "
                f"subscription {subscription.id}: {e}"
            )

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
        billing_period = metadata.get("billing_period", MONTHLY_PERIOD)

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

        # Resolve the exact price that was paid for; it carries the periodicity,
        # the currency and the amount the client agreed to
        currency_id = metadata.get("currency_id", DEFAULT_CURRENCY)
        commitment_id = metadata.get("commitment_id", NO_COMMITMENT)
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        version = await session.get(plan_version_entity, plan_version_id)
        price = (
            version.price_for(billing_period, currency_id, commitment_id)
            if version else None
        )

        if not price:
            logger.critical(
                f"Payment {payment.id} for client {client_id} refers to plan version "
                f"{plan_version_id} with no price for "
                f"{billing_period}/{currency_id}/{commitment_id}. "
                f"Manual intervention required."
            )
            return

        now = datetime.now(timezone.utc)
        period_start = now
        period_end = calculate_period_end(now, price.period.interval_months)

        # A commitment runs from the first payment of a term, so this candidate
        # end date is only applied when no term is running
        commitment_end = None
        if price.commitment.is_binding:
            commitment_end = calculate_period_end(now, price.commitment.duration_months)

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
            plan_changed = subscription.plan_version_id != plan_version_id

            if plan_changed:
                subscription.plan_version_id = plan_version_id
                subscription.pending_plan_version_id = None
                logger.info(f"Updated subscription {subscription.id} to plan version {plan_version_id}")

            # Step 3 of the migration described on LicenseBillingMode: the first
            # successful payment is what proves the mode, so a client invoiced
            # until now is recorded as collected by the provider from here on
            subscription.billing_mode_id = PROVIDER_BILLING

            # Update billing period tracking
            subscription.plan_version_price_id = price.id
            subscription.current_period_start = period_start
            subscription.current_period_end = period_end
            # Co-termination: a commitment already running is never restarted by
            # a change of plan, and a term that has lapsed starts anew
            if not subscription.is_committed:
                subscription.commitment_end_date = commitment_end

            # Update provider subscription ID if needed
            if payment.subscription_id and not subscription.provider_subscription_id:
                subscription.provider_subscription_id = payment.subscription_id

            subscription_service = cls.app_manager.get_service("subscription")
            await cls._grant_claimed_discount(
                subscription_service, subscription, metadata.get("discount_id"), session
            )
            await subscription_service.settle_terms(subscription, price, session)

            # Align the recurring collection with what is now owed, otherwise
            # Mollie keeps charging the previous amount. Settled first on
            # purpose: the discount granted a few lines above is part of it.
            if plan_changed and subscription.provider_subscription_id and client \
                    and client.provider_customer_id:
                checkout_service = cls.app_manager.get_service("mollie_checkout")
                currency = price.currency
                checkout_service.update_subscription_amount(
                    customer_id=client.provider_customer_id,
                    provider_subscription_id=subscription.provider_subscription_id,
                    currency_id=price.currency_id,
                    value=(
                        f"{currency.to_major_unit(subscription.amount_due):.{currency.minor_unit}f}"
                        if subscription.amount_due is not None else price.major_unit_value
                    ),
                    interval_months=price.period.interval_months
                )
        else:
            # New subscription
            subscription = subscription_entity(
                client_id=client_id,
                plan_version_id=plan_version_id,
                plan_version_price_id=price.id,
                billing_mode_id=PROVIDER_BILLING,
                provider_subscription_id=payment.subscription_id,
                current_period_start=period_start,
                current_period_end=period_end,
                commitment_end_date=commitment_end
            )
            session.add(subscription)
            await session.flush()

            subscription_service = cls.app_manager.get_service("subscription")
            await cls._grant_claimed_discount(
                subscription_service, subscription, metadata.get("discount_id"), session
            )
            await subscription_service.settle_terms(subscription, price, session)
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
                    session=session,
                    currency_id=metadata.get("currency_id", DEFAULT_CURRENCY),
                    commitment_id=metadata.get("commitment_id", NO_COMMITMENT),
                    amount_due=subscription.amount_due
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

        # Resolve context data for email/notification
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        plan_version = await session.get(plan_version_entity, plan_version_id)
        plan_name = plan_version.plan.id if plan_version and plan_version.plan else None
        if not client:
            stmt = select(client_entity).where(client_entity.id == client_id)
            result = await session.execute(stmt)
            client = result.scalar_one_or_none()
        client_name = client.name if client else None
        amount_str = str(payment.amount["value"]) if hasattr(payment, "amount") else None
        currency_str = payment.amount["currency"] if hasattr(payment, "amount") else None

        # Trigger payment success event (notification + email)
        trigger_event.delay(
            event_type=SUBSCRIPTION_PAYMENT_SUCCESS,
            user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
            email_context={
                "client_name": client_name,
                "plan_name": plan_name,
                "amount": amount_str,
                "currency": currency_str,
                "billing_period": billing_period,
                "next_billing_date": period_end.isoformat() if period_end else None,
                "front_url": settings.front_url,
            },
            notification_data={
                "client_name": client_name,
                "plan_name": plan_name,
                "billing_period": billing_period,
                "amount": amount_str,
                "currency": currency_str,
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
            # Resolve context data for email/notification
            plan_version_entity = cls.app_manager.get_entity("license_plan_version")
            client_entity = cls.app_manager.get_entity("client")
            plan_version = await session.get(plan_version_entity, plan_version_id) if plan_version_id else None
            plan_name = plan_version.plan.id if plan_version and plan_version.plan else None
            stmt = select(client_entity).where(client_entity.id == client_id)
            result = await session.execute(stmt)
            client = result.scalar_one_or_none()
            client_name = client.name if client else None
            amount_str = str(payment.amount["value"]) if hasattr(payment, "amount") else None
            currency_str = payment.amount["currency"] if hasattr(payment, "amount") else None
            error_reason = (
                getattr(payment, "details", {}).get("failureReason")
                if hasattr(payment, "details") else None
            )

            # Trigger payment failed event (notification + email)
            trigger_event.delay(
                event_type=SUBSCRIPTION_PAYMENT_FAILED,
                user_id=None,  # No specific user, sent to LICENSE_ADMIN_ROLE
                email_context={
                    "client_name": client_name,
                    "plan_name": plan_name,
                    "amount": amount_str,
                    "currency": currency_str,
                    "error_reason": error_reason,
                    "front_url": settings.front_url,
                },
                notification_data={
                    "client_name": client_name,
                    "plan_name": plan_name,
                    "amount": amount_str,
                    "currency": currency_str,
                    "error_reason": error_reason,
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
    async def _amount_to_charge(
        cls,
        price: "LicensePlanVersionPrice",
        discount_id: Optional[str],
        session: AsyncSession
    ) -> str:
        """What the provider must actually collect for one period.

        The catalogue price is what the offer costs; a claimed discount is taken
        off it before the payment is created. Charging the full price and
        recording a reduced amount would have the client pay what nobody agreed
        to, and no later correction would give the money back on its own.

        An unknown or withdrawn discount charges the full price rather than
        failing: the claim is settled again when the payment is confirmed, and
        refusing a payment over a commercial detail costs more than collecting
        the catalogue amount.
        """
        if not discount_id:
            return price.major_unit_value

        discount_entity = cls.app_manager.get_entity("license_discount")
        discount = await session.get(discount_entity, discount_id)

        # The same rule as the one that grants it: charging a reduced amount for
        # a discount the grant would refuse under-bills the first payment, and
        # nothing later gives that money back.
        if discount is None or not discount.enabled or discount.grant_id != MANUAL_GRANT:
            logger.warning(
                f"Discount {discount_id} claimed at checkout cannot be claimed; "
                f"charging the catalogue price"
            )
            return price.major_unit_value

        amount = discounted_amount(price.amount, discount.value, discount.unit_id)
        currency = price.currency

        return f"{currency.to_major_unit(amount):.{currency.minor_unit}f}"

    @classmethod
    async def create_payment(
        cls,
        client_id: str,
        plan_version_id: str,
        billing_period: str,
        redirect_url: str,
        webhook_url: str,
        session: AsyncSession,
        cancel_url: Optional[str] = None,
        currency_id: str = DEFAULT_CURRENCY,
        commitment_id: str = NO_COMMITMENT,
        discount_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a Mollie payment for subscription.

        Args:
            client_id: Client ID
            plan_version_id: Plan version to subscribe to
            billing_period: Price period ID (e.g., "MONTHLY")
            redirect_url: URL to redirect after payment (success/pending/failed)
            webhook_url: URL for Mollie webhooks
            session: Database session
            cancel_url: URL to redirect if user cancels (optional)
            currency_id: Currency to charge in
            commitment_id: Contractual commitment subscribed to
            discount_id: Discount claimed at checkout, carried in the payment
                metadata and granted once the payment is confirmed — never
                before, since an abandoned checkout must leave nothing behind

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

        # Get price for the requested period and currency
        price = version.price_for(billing_period, currency_id, commitment_id)

        if not price or not price.amount:
            logger.error(
                f"Plan version {plan_version_id} has no price for "
                f"{billing_period}/{currency_id}/{commitment_id}"
            )
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
                    "currency": price.currency_id,
                    "value": await cls._amount_to_charge(price, discount_id, session)
                },
                "description": f"{version.plan_id} - {billing_period}",
                "redirectUrl": redirect_url,
                "webhookUrl": webhook_url,
                # Mollie returns the metadata whenever the payment is fetched,
                # which is how the webhook knows what was subscribed to. It is
                # deliberately set on the payment and not on the recurring
                # subscription: Mollie forwards a subscription's metadata to
                # every payment it generates, so a discount declared there would
                # be granted again at each renewal — including after the
                # commitment ended it. Roughly 1kB is allowed, this stays far
                # below.
                "metadata": {
                    "client_id": client_id,
                    "plan_version_id": plan_version_id,
                    "billing_period": billing_period,
                    "currency_id": price.currency_id,
                    "commitment_id": price.commitment_id,
                    "discount_id": discount_id
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
        session: AsyncSession,
        currency_id: str = DEFAULT_CURRENCY,
        commitment_id: str = NO_COMMITMENT,
        amount_due: Optional[int] = None
    ) -> Optional[str]:
        """
        Create a recurring Mollie subscription.

        Called after first payment is successful and mandate is created.

        Args:
            customer_id: Mollie customer ID
            plan_version_id: Plan version to subscribe to
            billing_period: Price period ID (e.g., "MONTHLY")
            webhook_url: URL for Mollie webhooks
            session: Database session
            currency_id: Currency to charge in
            commitment_id: Contractual commitment subscribed to
            amount_due: What the client actually owes per period, discount
                included. Every renewal is collected on this amount, so leaving
                it out would silently charge the catalogue price for years

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

        price = version.price_for(billing_period, currency_id, commitment_id)

        if not price or not price.amount:
            logger.error(
                f"Plan version {plan_version_id} has no price for "
                f"{billing_period}/{currency_id}/{commitment_id}"
            )
            return None

        try:
            customer = mollie.customers.get(customer_id)
            currency = price.currency
            recurring_value = (
                f"{currency.to_major_unit(amount_due):.{currency.minor_unit}f}"
                if amount_due is not None else price.major_unit_value
            )

            subscription = customer.subscriptions.create(data={
                "amount": {
                    "currency": price.currency_id,
                    "value": recurring_value
                },
                "interval": f"{price.period.interval_months} months",
                "description": f"{version.plan_id} subscription",
                "webhookUrl": webhook_url,
                "metadata": {
                    "plan_version_id": plan_version_id,
                    "currency_id": price.currency_id,
                    "commitment_id": price.commitment_id
                }
            })

            return subscription.id

        except MollieError as e:
            logger.error(f"Error creating Mollie subscription: {e}")
            return None

    @classmethod
    def update_subscription_amount(
        cls,
        customer_id: str,
        provider_subscription_id: str,
        currency_id: str,
        value: str,
        interval_months: int
    ) -> bool:
        """
        Align a recurring Mollie subscription with new billing terms.

        Called whenever the plan a client pays for changes, so that the amount
        collected matches the plan actually granted. Mollie refuses to update a
        canceled subscription, so this must run before any cancellation.

        Takes plain values rather than a price entity, so that callers holding a
        detached or expired entity cannot trigger a lazy load here. It performs
        no database access and is safe to call from both async services and
        synchronous background tasks.

        Args:
            customer_id: Mollie customer ID
            provider_subscription_id: Mollie subscription ID
            currency_id: ISO 4217 currency code
            value: Amount in major units, as a decimal string
            interval_months: Length of the billing period in months

        Returns:
            True if the subscription was updated
        """
        mollie = get_mollie_client()
        if not mollie:
            logger.error("Mollie not configured, cannot update subscription")
            return False

        try:
            customer = mollie.customers.get(customer_id)
            customer.subscriptions.update(provider_subscription_id, data={
                "amount": {
                    "currency": currency_id,
                    "value": value
                },
                "interval": f"{interval_months} months"
            })
            return True

        except MollieError as e:
            logger.error(
                f"Error updating Mollie subscription {provider_subscription_id}: {e}"
            )
            return False

    @classmethod
    def cancel_provider_subscription(
        cls,
        customer_id: str,
        provider_subscription_id: str
    ) -> bool:
        """
        Stop a recurring Mollie subscription.

        This method performs no database access and is safe to call from both
        async services and synchronous background tasks.

        Args:
            customer_id: Mollie customer ID
            provider_subscription_id: Mollie subscription ID

        Returns:
            True if the subscription was canceled
        """
        mollie = get_mollie_client()
        if not mollie:
            logger.error("Mollie not configured, cannot cancel subscription")
            return False

        try:
            customer = mollie.customers.get(customer_id)
            customer.subscriptions.delete(provider_subscription_id)
            return True

        except MollieError as e:
            logger.error(
                f"Error canceling Mollie subscription {provider_subscription_id}: {e}"
            )
            return False
