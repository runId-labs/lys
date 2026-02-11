"""
Pydantic models for user_role emailing fixtures validation.
"""
from typing import List

from lys.core.models.fixtures import ParametricEntityFixturesModel


class EmailingTypeFixturesModel(ParametricEntityFixturesModel):
    """Pydantic model for validating EmailingType fixture data with roles."""

    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        roles: List[str] = []

    attributes: AttributesModel