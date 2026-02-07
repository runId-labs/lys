"""
Pydantic models for Mollie webservices.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo
from strawberry import relay

from lys.apps.licensing.consts import BillingPeriod


@dataclass
class SubscribeToPlanResult:
    """Result of subscribe_to_plan operation."""
    success: bool
    checkout_url: Optional[str] = None  # If payment required
    effective_date: Optional[datetime] = None  # If scheduled for later
    prorata_amount: Optional[int] = None  # Amount in cents (for display)
    error: Optional[str] = None


@dataclass
class CancelSubscriptionResult:
    """Result of cancel_subscription operation."""
    success: bool
    effective_date: Optional[datetime] = None  # When cancellation takes effect
    error: Optional[str] = None


class SubscribeToPlanInputModel(BaseModel):
    """Input model for subscribing to a plan."""
    plan_version_id: str
    billing_period: BillingPeriod
    success_url: str

    @field_validator("plan_version_id", mode="before")
    @classmethod
    def validate_plan_version_id(cls, value: relay.GlobalID | dict | str, info: ValidationInfo) -> str:
        """Extract node_id from GlobalID."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return value.get("node_id")
        return value.node_id