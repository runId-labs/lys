"""
Pydantic models for the license plan module.

This module provides the fixture validation models used to load:
- LicenseCurrency: currencies available for pricing
- LicensePricePeriod: billing periodicities
- LicenseCommitment: contractual commitments
- LicensePlanVersion: plan versions with their prices and rules
"""

from typing import Any, Dict, List

from lys.core.models.fixtures import EntityFixturesModel, ParametricEntityFixturesModel


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
