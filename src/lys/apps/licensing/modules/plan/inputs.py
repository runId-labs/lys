"""
Strawberry inputs for the plan version webservices.
"""

import strawberry
from strawberry import relay

from lys.apps.licensing.modules.plan.models import (
    CreatePlanVersionInputModel,
    PlanVersionPriceInputModel,
    PlanVersionRuleInputModel,
    SetPlanVersionRuleInputModel,
)


@strawberry.experimental.pydantic.input(model=PlanVersionPriceInputModel)
class PlanVersionPriceInput:
    period_id: strawberry.auto = strawberry.field(
        description="Billing periodicity this price applies to"
    )
    amount: strawberry.auto = strawberry.field(
        description="Price in currency minor units, for one billing period"
    )
    currency_id: strawberry.auto = strawberry.field(
        description="Currency of the amount (ISO 4217 code, defaults to EUR)"
    )
    commitment_id: strawberry.auto = strawberry.field(
        description="Commitment this price is offered against (defaults to none)"
    )


@strawberry.experimental.pydantic.input(model=PlanVersionRuleInputModel)
class PlanVersionRuleInput:
    rule_id: strawberry.auto = strawberry.field(
        description="Rule to grant on the version"
    )
    limit_value: strawberry.auto = strawberry.field(
        description="Limit value; null means unlimited for a quota, or a feature toggle"
    )


@strawberry.experimental.pydantic.input(model=CreatePlanVersionInputModel)
class CreatePlanVersionInput:
    plan_id: strawberry.auto = strawberry.field(
        description="Plan to publish a new version of"
    )
    prices: list[PlanVersionPriceInput] = strawberry.field(
        default_factory=list,
        description="Prices of the version; an empty list produces a free version"
    )
    rules: list[PlanVersionRuleInput] = strawberry.field(
        default_factory=list,
        description="Rules the version grants, with their limits"
    )


@strawberry.experimental.pydantic.input(model=SetPlanVersionRuleInputModel)
class SetPlanVersionRuleInput:
    plan_version_id: relay.GlobalID = strawberry.field(
        description="Plan version to set the rule on"
    )
    rule_id: strawberry.auto = strawberry.field(
        description="Rule to set a limit for"
    )
    limit_value: strawberry.auto = strawberry.field(
        description="Limit value; null means unlimited for a quota, or a feature toggle"
    )
