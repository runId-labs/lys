"""
Mollie webservices for subscription management.

Contains:
- REST webhook endpoint for Mollie payment notifications
- GraphQL mutations for subscription management
"""

import logging

import strawberry
from fastapi import APIRouter, HTTPException, Request
from mollie.api.error import Error as MollieError
from sqlalchemy import select

from lys.apps.licensing.consts import (
    AUTHENTICATION_REQUIRED_ERROR,
    NOT_CLIENT_ASSOCIATED_USER_ERROR,
)
from lys.apps.licensing.modules.mollie.inputs import SubscribeToPlanInput
from lys.apps.licensing.modules.mollie.nodes import (
    CancelSubscriptionResultNode,
    SubscribeToPlanResultNode,
)
from lys.apps.licensing.modules.mollie.services import (
    get_mollie_client,
    get_webhook_base_url,
)
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation
from lys.core.graphql.types import Mutation
from lys.core.managers.app import LysAppManager

logger = logging.getLogger(__name__)


def get_app_manager():
    """Get the singleton app_manager instance."""
    return LysAppManager()


router = APIRouter(prefix="/webhooks", tags=["mollie"])


# =============================================================================
# REST Webhook Endpoint
# =============================================================================

@router.post("/mollie")
async def mollie_webhook(request: Request):
    """
    Handle incoming Mollie webhook notifications.

    Mollie sends webhooks for:
    - payment.paid: Payment completed
    - payment.failed: Payment failed
    - payment.expired: Payment expired
    - payment.canceled: Payment canceled
    - subscription.created: Subscription created
    - subscription.updated: Subscription updated
    - subscription.cancelled: Subscription cancelled

    IMPORTANT: Mollie only sends the payment/subscription ID.
    We must fetch full details from the API.

    Security: Mollie only sends the resource ID in the webhook. We always
    re-fetch the full resource from the Mollie API using our API key, so
    forged webhooks cannot inject fake data.
    """
    app_manager = get_app_manager()

    # Parse form data (Mollie sends as form, not JSON)
    form_data = await request.form()
    resource_id = form_data.get("id")

    if not resource_id:
        logger.warning("Mollie webhook received without ID")
        raise HTTPException(status_code=400, detail="Missing resource ID")

    logger.info(f"Received Mollie webhook for: {resource_id}")

    # Idempotency check via Redis
    if app_manager.pubsub:
        cache_key = f"mollie_webhook:{resource_id}"
        is_new = await app_manager.pubsub.set_if_not_exists(
            cache_key, "1", ttl_seconds=86400  # 24 hours
        )

        if not is_new:
            logger.info(f"Mollie webhook {resource_id} already processed, skipping")
            return {"status": "ok", "handled": False, "reason": "duplicate"}

    # Get Mollie client
    mollie_client = get_mollie_client()
    if not mollie_client:
        logger.error("Mollie not configured")
        raise HTTPException(status_code=500, detail="Mollie not configured")

    # Process the webhook with database session
    try:
        async with app_manager.database.get_session() as session:
            # Determine resource type and fetch full data from Mollie
            if resource_id.startswith("tr_"):
                # Payment
                resource = mollie_client.payments.get(resource_id)
                resource_type = "payment"

            elif resource_id.startswith("sub_"):
                # Subscription - lookup customer_id from our DB
                subscription_entity = app_manager.get_entity("subscription")
                client_entity = app_manager.get_entity("client")

                stmt = select(subscription_entity).where(
                    subscription_entity.provider_subscription_id == resource_id
                )
                result = await session.execute(stmt)
                db_subscription = result.scalar_one_or_none()

                if not db_subscription:
                    logger.warning(f"Subscription {resource_id} not found in database")
                    return {"status": "ok", "handled": False, "reason": "subscription_not_found"}

                # Get customer_id from client
                client = await session.get(client_entity, db_subscription.client_id)
                if not client or not client.provider_customer_id:
                    logger.warning(f"No customer_id for subscription {resource_id}")
                    return {"status": "ok", "handled": False, "reason": "no_customer_id"}

                customer = mollie_client.customers.get(client.provider_customer_id)
                resource = customer.subscriptions.get(resource_id)
                resource_type = "subscription"

            elif resource_id.startswith("ord_"):
                # Order
                resource = mollie_client.orders.get(resource_id)
                resource_type = "order"

            else:
                logger.warning(f"Unknown Mollie resource type: {resource_id}")
                return {"status": "ok", "handled": False, "reason": "unknown_type"}

            # Process the webhook
            webhook_service = app_manager.get_service("mollie_webhook")
            result = await webhook_service.handle_webhook(
                resource_type=resource_type,
                resource=resource,
                session=session
            )
            await session.commit()
            return {"status": "ok", "handled": result["handled"]}

    except MollieError as e:
        logger.error(f"Error fetching Mollie resource {resource_id}: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error")

    except Exception as e:
        logger.exception(f"Error processing Mollie webhook {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error")


# =============================================================================
# GraphQL Mutations
# =============================================================================

async def get_client_for_user(info: Info):
    """
    Get the client associated with the authenticated user.

    Returns:
        (client, error) tuple - client if found, error string if not
    """
    connected_user = info.context.connected_user
    if not connected_user:
        return None, AUTHENTICATION_REQUIRED_ERROR

    user_id = connected_user["sub"]
    session = info.context.session
    client_entity = info.context.app_manager.get_entity("client")
    user_entity = info.context.app_manager.get_entity("user")

    # Check if user is owner of a client
    stmt = select(client_entity).where(client_entity.owner_id == user_id)
    result = await session.execute(stmt)
    client = result.scalar_one_or_none()

    # If not owner, check if user is member of a client (via user.client_id)
    if not client:
        stmt = select(user_entity).where(user_entity.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user and user.client_id:
            client = await session.get(client_entity, user.client_id)

    if not client:
        return None, NOT_CLIENT_ASSOCIATED_USER_ERROR

    return client, None


@register_mutation()
@strawberry.type
class MollieMutation(Mutation):

    @lys_field(
        ensure_type=SubscribeToPlanResultNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Subscribe to a plan (handles new subscription, upgrade, and downgrade)"
    )
    async def subscribe_to_plan(
        self,
        info: Info,
        input: SubscribeToPlanInput
    ):
        """
        Subscribe to a plan.

        Automatically handles:
        - New subscription or FREE → Paid: Creates checkout session
        - Upgrade: Calculates prorata and creates payment
        - Downgrade: Schedules change for end of billing period
        """
        # Get client for authenticated user
        client, error = await get_client_for_user(info)
        if error:
            return SubscribeToPlanResultNode(success=False, error=error)

        # Build webhook URL
        webhook_base = get_webhook_base_url()
        if not webhook_base:
            webhook_base = str(info.context.request.base_url).rstrip("/")
        webhook_url = f"{webhook_base}/webhooks/mollie"

        # Call service
        data = input.to_pydantic()
        subscription_service = info.context.app_manager.get_service("subscription")
        result = await subscription_service.subscribe_to_plan(
            client_id=client.id,
            plan_version_id=data.plan_version_id,
            billing_period=data.billing_period.value,
            success_url=data.success_url,
            webhook_url=webhook_url,
            session=info.context.session
        )

        return SubscribeToPlanResultNode(
            success=result.success,
            checkout_url=result.checkout_url,
            effective_date=result.effective_date,
            prorata_amount=result.prorata_amount,
            error=result.error
        )

    @lys_field(
        ensure_type=CancelSubscriptionResultNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Cancel subscription (takes effect at end of current period)"
    )
    async def cancel_subscription(self, info: Info):
        """
        Cancel the subscription.

        The cancellation takes effect at the end of the current billing period.
        The user keeps access until then, then downgrades to FREE plan.
        """
        # Get client for authenticated user
        client, error = await get_client_for_user(info)
        if error:
            return CancelSubscriptionResultNode(success=False, error=error)

        # Call service
        subscription_service = info.context.app_manager.get_service("subscription")
        result = await subscription_service.cancel(
            client_id=client.id,
            session=info.context.session
        )

        return CancelSubscriptionResultNode(
            success=result.success,
            effective_date=result.effective_date,
            error=result.error
        )