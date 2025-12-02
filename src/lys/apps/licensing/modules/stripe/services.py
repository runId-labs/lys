"""
Stripe services for licensing module.

This module provides:
- StripeSyncService: Synchronize license plans with Stripe
- StripeWebhookService: Handle Stripe webhook events
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.core.configs import settings
from lys.core.registries import register_service
from lys.core.services import Service

logger = logging.getLogger(__name__)


@register_service()
class StripeSyncService(Service):
    """
    Service for synchronizing license plans with Stripe.

    Creates Stripe Products and Prices for paid plan versions.
    Free plans are skipped (no Stripe products needed).

    Usage:
        # Sync a single plan version
        await StripeSyncService.sync_plan_version(version_id, session)

        # Sync all enabled versions (typically called after fixtures)
        await StripeSyncService.sync_all_enabled_versions(session)
    """

    service_name = "stripe_sync"

    @classmethod
    def _get_stripe(cls):
        """
        Get configured Stripe module.

        Returns:
            stripe module or None if not configured

        Raises:
            ImportError: If stripe package is not installed
        """
        if not settings.stripe.configured():
            logger.debug("Stripe not configured, skipping sync")
            return None

        try:
            import stripe
            stripe.api_key = settings.stripe.api_key
            return stripe
        except ImportError:
            logger.warning("stripe package not installed. Run: pip install stripe")
            return None

    @classmethod
    async def sync_plan_version(
        cls,
        plan_version_id: str,
        session: AsyncSession
    ) -> bool:
        """
        Synchronize a plan version with Stripe.

        Creates a Stripe Product and Prices (monthly/yearly) if they don't exist.
        Updates the plan version's stripe_product_id.

        Args:
            plan_version_id: The plan version ID to sync
            session: Database session

        Returns:
            True if sync was successful, False if skipped or failed
        """
        stripe = cls._get_stripe()
        if not stripe:
            return False

        # Get plan version
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        version = await session.get(plan_version_entity, plan_version_id)

        if not version:
            logger.warning(f"Plan version {plan_version_id} not found")
            return False

        # Skip free plans
        if version.is_free:
            logger.debug(f"Skipping free plan version {version.plan_id} v{version.version}")
            return True

        # Skip if already synced
        if version.stripe_product_id:
            logger.debug(f"Plan version {version.plan_id} v{version.version} already synced")
            return True

        try:
            # Create Stripe Product
            product = stripe.Product.create(
                name=f"{version.plan_id} v{version.version}",
                description=f"License plan {version.plan_id} version {version.version}",
                metadata={
                    "plan_id": version.plan_id,
                    "version": str(version.version),
                    "plan_version_id": version.id
                }
            )

            # Create monthly price if defined
            if version.price_monthly:
                stripe.Price.create(
                    product=product.id,
                    unit_amount=version.price_monthly,
                    currency=version.currency,
                    recurring={"interval": "month"},
                    metadata={
                        "plan_version_id": version.id,
                        "billing_period": "monthly"
                    }
                )

            # Create yearly price if defined
            if version.price_yearly:
                stripe.Price.create(
                    product=product.id,
                    unit_amount=version.price_yearly,
                    currency=version.currency,
                    recurring={"interval": "year"},
                    metadata={
                        "plan_version_id": version.id,
                        "billing_period": "yearly"
                    }
                )

            # Update plan version with Stripe product ID
            version.stripe_product_id = product.id
            await session.flush()

            logger.info(
                f"Synced plan {version.plan_id} v{version.version} "
                f"to Stripe product {product.id}"
            )
            return True

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error syncing plan version {plan_version_id}: {e}")
            return False

    @classmethod
    async def sync_all_enabled_versions(cls, session: AsyncSession) -> List[str]:
        """
        Synchronize all enabled plan versions with Stripe.

        Iterates through all enabled plan versions and syncs each one.
        Free plans are automatically skipped.

        Args:
            session: Database session

        Returns:
            List of successfully synced plan version IDs
        """
        stripe = cls._get_stripe()
        if not stripe:
            return []

        plan_version_entity = cls.app_manager.get_entity("license_plan_version")

        # Get all enabled versions
        stmt = select(plan_version_entity).where(
            plan_version_entity.enabled == True
        )
        result = await session.execute(stmt)
        versions = list(result.scalars().all())

        synced_ids = []
        for version in versions:
            if await cls.sync_plan_version(version.id, session):
                if not version.is_free:  # Only count paid plans
                    synced_ids.append(version.id)

        logger.info(f"Synced {len(synced_ids)} paid plan versions to Stripe")
        return synced_ids

    @classmethod
    async def get_stripe_prices(
        cls,
        plan_version_id: str,
        session: AsyncSession
    ) -> Optional[dict]:
        """
        Get Stripe prices for a plan version.

        Args:
            plan_version_id: The plan version ID
            session: Database session

        Returns:
            Dict with 'monthly' and 'yearly' price IDs, or None if not synced
        """
        stripe = cls._get_stripe()
        if not stripe:
            return None

        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        version = await session.get(plan_version_entity, plan_version_id)

        if not version or not version.stripe_product_id:
            return None

        try:
            # List prices for this product
            prices = stripe.Price.list(product=version.stripe_product_id, active=True)

            result = {"monthly": None, "yearly": None}
            for price in prices.data:
                if price.recurring:
                    if price.recurring.interval == "month":
                        result["monthly"] = price.id
                    elif price.recurring.interval == "year":
                        result["yearly"] = price.id

            return result

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting prices for {plan_version_id}: {e}")
            return None

    @classmethod
    async def create_checkout_session(
        cls,
        client_id: str,
        plan_version_id: str,
        billing_period: str,
        session: AsyncSession,
        success_url: str,
        cancel_url: str
    ) -> Optional[str]:
        """
        Create a Stripe Checkout session for subscription.

        Args:
            client_id: The client ID
            plan_version_id: The plan version to subscribe to
            billing_period: "monthly" or "yearly"
            session: Database session
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment

        Returns:
            Checkout session URL or None if failed
        """
        stripe_module = cls._get_stripe()
        if not stripe_module:
            return None

        # Get prices
        prices = await cls.get_stripe_prices(plan_version_id, session)
        if not prices:
            logger.error(f"No Stripe prices found for plan version {plan_version_id}")
            return None

        price_id = prices.get(billing_period)
        if not price_id:
            logger.error(f"No {billing_period} price for plan version {plan_version_id}")
            return None

        # Get or create Stripe customer for client
        client_entity = cls.app_manager.get_entity("client")
        client = await session.get(client_entity, client_id)

        if not client:
            logger.error(f"Client {client_id} not found")
            return None

        try:
            # Create or get customer
            if not client.stripe_customer_id:
                customer = stripe_module.Customer.create(
                    metadata={"client_id": client_id}
                )
                client.stripe_customer_id = customer.id
                await session.flush()

            customer_id = client.stripe_customer_id

            # Create checkout session
            checkout_session = stripe_module.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "client_id": client_id,
                    "plan_version_id": plan_version_id,
                    "billing_period": billing_period
                }
            )

            return checkout_session.url

        except stripe_module.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            return None


@register_service()
class StripeWebhookService(Service):
    """
    Service for handling Stripe webhook events.

    Processes events sent by Stripe to update subscription state.
    Called by the REST webhook endpoint in mimir-api.

    Handled events:
    - checkout.session.completed: New subscription created via Checkout
    - invoice.payment_succeeded: Subscription renewed, apply pending changes
    - invoice.payment_failed: Payment failed, notify client
    - customer.subscription.updated: Plan changed or cancelled
    - customer.subscription.deleted: Subscription ended, downgrade to FREE
    """

    service_name = "stripe_webhook"

    EVENT_HANDLERS = {
        "checkout.session.completed": "_handle_checkout_completed",
        "invoice.payment_succeeded": "_handle_payment_succeeded",
        "invoice.payment_failed": "_handle_payment_failed",
        "customer.subscription.updated": "_handle_subscription_updated",
        "customer.subscription.deleted": "_handle_subscription_deleted",
    }

    @classmethod
    async def handle_event(
        cls,
        event_type: str,
        event_data: Dict[str, Any],
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Main entry point for processing Stripe webhook events.

        Args:
            event_type: Stripe event type (e.g., "checkout.session.completed")
            event_data: Event data from Stripe (event.data.object)
            session: Database session

        Returns:
            Dict with processing result: {"handled": bool, "message": str}
        """
        handler_name = cls.EVENT_HANDLERS.get(event_type)

        if not handler_name:
            logger.debug(f"Unhandled Stripe event type: {event_type}")
            return {"handled": False, "message": f"Event type {event_type} not handled"}

        handler = getattr(cls, handler_name)

        try:
            await handler(event_data, session)
            logger.info(f"Successfully processed Stripe event: {event_type}")
            return {"handled": True, "message": "Event processed successfully"}
        except Exception as e:
            logger.error(f"Error processing Stripe event {event_type}: {str(e)}")
            raise

    @classmethod
    async def _handle_checkout_completed(
        cls,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> None:
        """
        Handle checkout.session.completed event.

        Links the Stripe subscription to our Subscription entity.
        """
        subscription_entity = cls.app_manager.get_entity("subscription")
        client_entity = cls.app_manager.get_entity("client")

        stripe_subscription_id = data.get("subscription")
        stripe_customer_id = data.get("customer")
        metadata = data.get("metadata", {})

        client_id = metadata.get("client_id")
        plan_version_id = metadata.get("plan_version_id")

        if not client_id:
            logger.warning("checkout.session.completed missing client_id in metadata")
            return

        # Find existing subscription for this client
        stmt = select(subscription_entity).where(
            subscription_entity.client_id == client_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            # Update existing subscription with Stripe IDs
            subscription.stripe_subscription_id = stripe_subscription_id
            if plan_version_id:
                subscription.plan_version_id = plan_version_id
            logger.info(f"Updated subscription {subscription.id} with stripe_subscription_id")
        else:
            # Create new subscription
            if not plan_version_id:
                logger.error("Cannot create subscription: missing plan_version_id")
                return

            new_subscription = subscription_entity(
                client_id=client_id,
                plan_version_id=plan_version_id,
                stripe_subscription_id=stripe_subscription_id
            )
            session.add(new_subscription)
            logger.info(f"Created new subscription for client {client_id}")

        # Update client's stripe_customer_id if not set
        stmt = select(client_entity).where(client_entity.id == client_id)
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()

        if client and not client.stripe_customer_id:
            client.stripe_customer_id = stripe_customer_id
            logger.info(f"Updated client {client_id} with stripe_customer_id")

    @classmethod
    async def _handle_payment_succeeded(
        cls,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> None:
        """
        Handle invoice.payment_succeeded event.

        Applies pending plan changes (downgrades scheduled at period end).
        """
        stripe_subscription_id = data.get("subscription")

        if not stripe_subscription_id:
            return

        subscription_entity = cls.app_manager.get_entity("subscription")
        subscription_service = cls.app_manager.get_service("subscription")

        stmt = select(subscription_entity).where(
            subscription_entity.stripe_subscription_id == stripe_subscription_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(f"No subscription found for stripe_subscription_id={stripe_subscription_id}")
            return

        # Apply pending plan change if exists
        if subscription.pending_plan_version_id:
            await subscription_service.apply_pending_change(subscription.id, session)
            logger.info(f"Applied pending plan change for subscription {subscription.id}")

    @classmethod
    async def _handle_payment_failed(
        cls,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> None:
        """
        Handle invoice.payment_failed event.

        Logs warning. Email notification can be added later.
        """
        stripe_subscription_id = data.get("subscription")

        if not stripe_subscription_id:
            return

        subscription_entity = cls.app_manager.get_entity("subscription")

        stmt = select(subscription_entity).where(
            subscription_entity.stripe_subscription_id == stripe_subscription_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(f"No subscription found for stripe_subscription_id={stripe_subscription_id}")
            return

        logger.warning(
            f"Payment failed for subscription {subscription.id} (client_id={subscription.client_id})"
        )

    @classmethod
    async def _handle_subscription_updated(
        cls,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> None:
        """
        Handle customer.subscription.updated event.

        Logs subscription state changes.
        """
        stripe_subscription_id = data.get("id")
        cancel_at_period_end = data.get("cancel_at_period_end", False)
        status = data.get("status")

        subscription_entity = cls.app_manager.get_entity("subscription")

        stmt = select(subscription_entity).where(
            subscription_entity.stripe_subscription_id == stripe_subscription_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(f"No subscription found for stripe_subscription_id={stripe_subscription_id}")
            return

        logger.info(
            f"Subscription {subscription.id} updated: status={status}, "
            f"cancel_at_period_end={cancel_at_period_end}"
        )

    @classmethod
    async def _handle_subscription_deleted(
        cls,
        data: Dict[str, Any],
        session: AsyncSession
    ) -> None:
        """
        Handle customer.subscription.deleted event.

        Downgrades the client to FREE plan.
        """
        stripe_subscription_id = data.get("id")

        subscription_entity = cls.app_manager.get_entity("subscription")
        plan_version_service = cls.app_manager.get_service("license_plan_version")

        stmt = select(subscription_entity).where(
            subscription_entity.stripe_subscription_id == stripe_subscription_id
        )
        result = await session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            logger.warning(f"No subscription found for stripe_subscription_id={stripe_subscription_id}")
            return

        # Get FREE plan's current version
        from lys.apps.licensing.consts import FREE_PLAN

        free_version = await plan_version_service.get_current_version(FREE_PLAN, session)

        if not free_version:
            logger.error("FREE plan version not found, cannot downgrade")
            return

        # Downgrade to FREE plan
        subscription.plan_version_id = free_version.id
        subscription.stripe_subscription_id = None
        subscription.pending_plan_version_id = None

        logger.info(
            f"Subscription {subscription.id} cancelled, "
            f"downgraded to FREE plan for client {subscription.client_id}"
        )