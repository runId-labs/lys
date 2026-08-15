"""
Pydantic models for the license plan module.

This module provides:
- The fixture validation models used to load currencies, billing periodicities,
  contractual commitments and plan versions
- The input models of the plan version webservices
"""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from strawberry import relay

from lys.apps.licensing.consts import DEFAULT_CURRENCY, NO_COMMITMENT
from lys.core.models.fixtures import EntityFixturesModel, ParametricEntityFixturesModel


def _extract_node_id(value: "relay.GlobalID | dict | str") -> str:
    """Extract the raw entity ID from a Strawberry GlobalID."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("node_id")
    return value.node_id


class LicenseCurrencyFixturesModel(ParametricEntityFixturesModel):
    """Model for currency fixtures."""

    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        minor_unit: int = 2

    attributes: AttributesModel


class LicensePricePeriodFixturesModel(ParametricEntityFixturesModel):
    """Model for billing periodicity fixtures."""

    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        interval_months: int = 1

    attributes: AttributesModel


class LicenseCommitmentFixturesModel(ParametricEntityFixturesModel):
    """Model for contractual commitment fixtures."""

    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        duration_months: int = 0
        renewal_months: int = 0
        notice_months: int = 0

    attributes: AttributesModel


class LicensePlanVersionFixturesModel(EntityFixturesModel):
    """Model for plan version fixtures with prices and rules."""

    class AttributesModel(EntityFixturesModel.AttributesModel):
        plan_id: str
        version: int
        enabled: bool = True
        prices: List[Dict[str, Any]] = []
        rules: List[Dict[str, Any]] = []

    attributes: AttributesModel


class PlanVersionPriceInputModel(BaseModel):
    """One price of a plan version, for a given periodicity, currency and commitment."""

    period_id: str = Field(..., min_length=1)
    amount: int = Field(..., gt=0)
    currency_id: str = DEFAULT_CURRENCY
    commitment_id: str = NO_COMMITMENT


class PlanVersionRuleInputModel(BaseModel):
    """One rule of a plan version, with the limit it grants."""

    rule_id: str = Field(..., min_length=1)
    limit_value: int | None = Field(default=None, ge=0)


class CreatePlanVersionInputModel(BaseModel):
    """
    Input for publishing a new version of a plan.

    Prices and rules are published together: the new version becomes the offered
    one as soon as it is created, so publishing it without its rules would grant
    nothing to the clients landing on it.

    An empty price list produces a free version, which is what the free plan
    needs. Prices cannot be changed afterwards: a new version is published
    instead, so that existing subscribers keep the terms they agreed to.
    """

    plan_id: str = Field(..., min_length=1)
    prices: List[PlanVersionPriceInputModel] = []
    rules: List[PlanVersionRuleInputModel] = Field(..., min_length=1)


class SetPlanVersionRuleInputModel(BaseModel):
    """Input for setting the limit of a rule on a plan version."""

    plan_version_id: str
    rule_id: str = Field(..., min_length=1)
    limit_value: int | None = None

    @field_validator("plan_version_id", mode="before")
    @classmethod
    def validate_plan_version_id(cls, value, info: ValidationInfo) -> str:
        """Extract node_id from GlobalID."""
        return _extract_node_id(value)
