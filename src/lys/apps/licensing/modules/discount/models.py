"""
Pydantic models for the discount module.

This module provides:
- The fixture validation model used to load discounts
- The input models of the discount webservices
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from lys.apps.licensing.consts import PERCENT_UNIT
from lys.core.models.fixtures import ParametricEntityFixturesModel


class LicenseDiscountFixturesModel(ParametricEntityFixturesModel):
    """Model for discount fixtures."""

    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        value: int
        unit_id: str = PERCENT_UNIT
        grant_id: str

    attributes: AttributesModel


class CreateDiscountInputModel(BaseModel):
    """
    Input for declaring a discount in the catalogue.

    A discount is reference data with a business-meaningful code, so the code is
    supplied rather than generated: it is what a subscription refers to, and what
    an operator recognises in a receipt.
    """

    # The code is the primary key, and it travels into every receipt: it stays
    # readable and stable, so it is constrained here rather than sanitised later.
    code: str = Field(
        min_length=2,
        max_length=50,
        pattern=r"^[A-Z][A-Z0-9_]*$",
        description="Business code of the discount, upper case"
    )
    value: int = Field(gt=0, description="How much is taken off, read in the unit")
    unit_id: str = PERCENT_UNIT
    grant_id: str
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_value_for_unit(self):
        """Check the value against the unit it is read in.

        A percentage above 100 would owe the client money. Another unit will
        have its own bound, which is why this is validated against the unit
        rather than capped once and for all.
        """
        if self.unit_id == PERCENT_UNIT and self.value > 100:
            raise ValueError("A percentage discount cannot exceed 100")

        return self
