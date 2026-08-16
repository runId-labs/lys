"""
Strawberry inputs for the manual billing webservices.
"""

import strawberry
from strawberry import relay

from lys.apps.licensing.modules.subscription.models import SubscribeManuallyInputModel


@strawberry.experimental.pydantic.input(model=SubscribeManuallyInputModel)
class SubscribeManuallyInput:
    plan_version_price_id: relay.GlobalID = strawberry.field(
        description=(
            "Price agreed to, which identifies the plan version, the periodicity, "
            "the currency and the commitment"
        )
    )
