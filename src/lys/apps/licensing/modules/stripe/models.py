"""
Pydantic models for Stripe webservice inputs.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from strawberry import relay

from lys.core.utils.validators import validate_uuid


INVALID_PLAN_VERSION_ID = "INVALID_PLAN_VERSION_ID"


class BillingPeriodEnum(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CreateCheckoutSessionInputModel(BaseModel):
    """
    Input model for creating a Stripe Checkout session.
    """
    plan_version_id: str = Field(..., description="Plan version ID to subscribe to")
    billing_period: BillingPeriodEnum = Field(..., description="Billing period (monthly or yearly)")
    success_url: str = Field(..., description="URL to redirect to after successful payment")
    cancel_url: str = Field(..., description="URL to redirect to if user cancels")

    @field_validator('plan_version_id', mode='before')
    @classmethod
    def validate_plan_version_id(cls, value: relay.GlobalID | dict, info: ValidationInfo) -> str:
        if isinstance(value, dict):
            plan_version_id = value.get('node_id')
        else:
            plan_version_id = value.node_id
        validate_uuid(plan_version_id, INVALID_PLAN_VERSION_ID)
        return plan_version_id