"""
Stripe webservices for subscription management.

Contains:
- REST webhook endpoint for Stripe events
- GraphQL mutations for checkout and billing portal
"""

import logging

import stripe
import strawberry
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select

from lys.apps.licensing.consts import (
    AUTHENTICATION_REQUIRED_ERROR,
    CHECKOUT_SESSION_FAILED_ERROR,
    NO_STRIPE_CUSTOMER_ERROR,
    NOT_CLIENT_ASSOCIATED_USER_ERROR,
)
from lys.apps.licensing.modules.stripe.inputs import CreateCheckoutSessionInput
from lys.apps.licensing.modules.stripe.nodes import CheckoutSessionNode, BillingPortalNode
from lys.apps.licensing.modules.stripe.services import StripeSyncService, StripeWebhookService
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.configs import settings
from lys.core.contexts import Info
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation
from lys.core.graphql.types import Mutation
from lys.core.managers.app import LysAppManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["stripe"])


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle incoming Stripe webhook events.

    Stripe sends events for:
    - checkout.session.completed: Initial subscription creation
    - invoice.payment_succeeded: Recurring payment success
    - invoice.payment_failed: Payment failure
    - customer.subscription.updated: Plan changes
    - customer.subscription.deleted: Cancellation
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Verify Stripe signature and construct event
    stripe.api_key = settings.stripe.api_key
    try:

        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe.webhook_secret
        )
    except ImportError:
        logger.error("stripe package not installed")
        raise HTTPException(status_code=500, detail="Stripe not configured")
    except ValueError:
        logger.error("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Process the event
    event_type = event["type"]
    event_data = event["data"]["object"]

    logger.info(f"Received Stripe event: {event_type}")

    try:
        async with LysAppManager().database.get_session() as session:
            result = await StripeWebhookService.handle_event(event_type, event_data, session)
            await session.commit()
            return {"status": "ok", "handled": result["handled"]}
    except Exception as e:
        logger.exception(f"Error processing Stripe event {event_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# GraphQL Mutations
# =============================================================================

@register_mutation()
@strawberry.type
class StripeMutation(Mutation):

    @lys_field(
        ensure_type=CheckoutSessionNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Create a Stripe Checkout session for subscribing to a plan"
    )
    async def create_checkout_session(
        self,
        info: Info,
        input: CreateCheckoutSessionInput
    ):
        """
        Create a Stripe Checkout session.

        Redirects the user to Stripe's hosted checkout page.
        After payment, Stripe will redirect to success_url and send
        a webhook event to complete the subscription setup.
        """
        session = info.context.session
        data = input.to_pydantic()

        # Get client_id from authenticated user
        connected_user = info.context.connected_user
        if not connected_user:
            return CheckoutSessionNode(
                success=False,
                error=AUTHENTICATION_REQUIRED_ERROR
            )

        user_id = connected_user["sub"]

        # Find client where user is owner or member
        client_entity = info.context.app_manager.get_entity("client")
        client_user_entity = info.context.app_manager.get_entity("client_user")

        # Check if user is owner of a client
        stmt = select(client_entity).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()

        # If not owner, check if user is member of a client
        if not client:
            stmt = select(client_user_entity).where(client_user_entity.user_id == user_id)
            result = await session.execute(stmt)
            client_user = result.scalar_one_or_none()
            if client_user:
                client = await session.get(client_entity, client_user.client_id)

        if not client:
            return CheckoutSessionNode(
                success=False,
                error=NOT_CLIENT_ASSOCIATED_USER_ERROR
            )

        client_id = client.id

        checkout_url = await StripeSyncService.create_checkout_session(
            client_id=client_id,
            plan_version_id=data.plan_version_id,
            billing_period=data.billing_period.value,
            session=session,
            success_url=data.success_url,
            cancel_url=data.cancel_url
        )

        if not checkout_url:
            return CheckoutSessionNode(
                success=False,
                error=CHECKOUT_SESSION_FAILED_ERROR
            )

        return CheckoutSessionNode(
            success=True,
            checkout_url=checkout_url
        )

    @lys_field(
        ensure_type=BillingPortalNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Create a Stripe Billing Portal session for managing subscription"
    )
    async def create_billing_portal_session(
        self,
        info: Info,
        return_url: str
    ):
        """
        Create a Stripe Billing Portal session.

        Allows users to manage their subscription:
        - Update payment method
        - View invoices
        - Cancel subscription
        """
        session = info.context.session

        # Get client_id from authenticated user
        connected_user = info.context.connected_user
        if not connected_user:
            return BillingPortalNode(
                success=False,
                error=AUTHENTICATION_REQUIRED_ERROR
            )

        user_id = connected_user["sub"]

        # Find client where user is owner or member
        client_entity = info.context.app_manager.get_entity("client")
        client_user_entity = info.context.app_manager.get_entity("client_user")

        # Check if user is owner of a client
        stmt = select(client_entity).where(client_entity.owner_id == user_id)
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()

        # If not owner, check if user is member of a client
        if not client:
            stmt = select(client_user_entity).where(client_user_entity.user_id == user_id)
            result = await session.execute(stmt)
            client_user = result.scalar_one_or_none()
            if client_user:
                client = await session.get(client_entity, client_user.client_id)

        if not client:
            return BillingPortalNode(
                success=False,
                error=NOT_CLIENT_ASSOCIATED_USER_ERROR
            )

        if not client.stripe_customer_id:
            return BillingPortalNode(
                success=False,
                error=NO_STRIPE_CUSTOMER_ERROR
            )

        try:
            stripe.api_key = settings.stripe.api_key
            portal_session = stripe.billing_portal.Session.create(
                customer=client.stripe_customer_id,
                return_url=return_url
            )

            return BillingPortalNode(
                success=True,
                portal_url=portal_session.url
            )

        except Exception as e:
            logger.exception(f"Error creating billing portal session: {e}")
            return BillingPortalNode(
                success=False,
                error=str(e)
            )