"""
Strawberry inputs for Stripe webservices.
"""

from enum import Enum

import strawberry
from strawberry import relay

from lys.apps.licensing.modules.stripe.models import CreateCheckoutSessionInputModel


@strawberry.enum
class BillingPeriod(str, Enum):
    """GraphQL enum for billing period."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


@strawberry.experimental.pydantic.input(model=CreateCheckoutSessionInputModel)
class CreateCheckoutSessionInput:
    plan_version_id: relay.GlobalID = strawberry.field(
        description="Plan version ID to subscribe to"
    )
    billing_period: strawberry.auto = strawberry.field(
        description="Billing period (monthly or yearly)"
    )
    success_url: strawberry.auto = strawberry.field(
        description="URL to redirect to after successful payment"
    )
    cancel_url: strawberry.auto = strawberry.field(
        description="URL to redirect to if user cancels"
    )