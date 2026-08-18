"""
Pydantic models for the subscription module.

Input models of the manual billing webservices, used when collection is handled
outside the application.
"""

from typing import Optional

from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo
from strawberry import relay


def _extract_node_id(value: "relay.GlobalID | dict | str") -> str:
    """Extract the raw entity ID from a Strawberry GlobalID."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("node_id")
    return value.node_id


class SubscribeManuallyInputModel(BaseModel):
    """
    Input for placing a subscription on a plan billed outside the application.

    The subscription is resolved from the mutation id, and the price identifies
    the plan version, the periodicity, the currency and the commitment on its
    own: they are one row in the database and travel as one reference here.

    A discount may be granted in the same move. It is optional and travels apart
    from the price: what is owed comes from the catalogue, what is taken off it
    is a commercial decision.
    """

    plan_version_price_id: str
    discount_id: Optional[str] = None

    @field_validator("plan_version_price_id", mode="before")
    @classmethod
    def validate_plan_version_price_id(cls, value, info: ValidationInfo) -> str:
        """Extract node_id from GlobalID."""
        return _extract_node_id(value)
