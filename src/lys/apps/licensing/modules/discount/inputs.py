"""
Strawberry inputs for the discount webservices.
"""

import strawberry

from lys.apps.licensing.modules.discount.models import CreateDiscountInputModel


@strawberry.experimental.pydantic.input(model=CreateDiscountInputModel)
class CreateDiscountInput:
    code: strawberry.auto = strawberry.field(
        description="Business code of the discount, referred to when granting it"
    )
    value: strawberry.auto = strawberry.field(
        description="How much is taken off the price, read in the unit below"
    )
    unit_id: strawberry.auto = strawberry.field(
        description="How the value is expressed (defaults to a percentage)"
    )
    grant_id: strawberry.auto = strawberry.field(
        description="Who may offer it: the client during checkout, or an administrator"
    )
    description: strawberry.auto = strawberry.field(
        description="Human-readable description, shown when offering the discount"
    )
