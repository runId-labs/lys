"""
Strawberry inputs for Mollie webservices.
"""

import strawberry
from strawberry import relay

from lys.apps.licensing.consts import BillingPeriod
from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel

# Register enum with Strawberry
BillingPeriodGQL = strawberry.enum(BillingPeriod)


@strawberry.experimental.pydantic.input(model=SubscribeToPlanInputModel)
class SubscribeToPlanInput:
    plan_version_id: relay.GlobalID = strawberry.field(
        description="Plan version ID to subscribe to"
    )
    billing_period: strawberry.auto = strawberry.field(
        description="Billing period (monthly or yearly)"
    )
    success_url: strawberry.auto = strawberry.field(
        description="URL to redirect to after payment"
    )