"""
Pydantic models for licensing notification fixtures validation.
"""
from typing import List

from lys.core.models.fixtures import ParametricEntityFixturesModel


class NotificationTypeFixturesModel(ParametricEntityFixturesModel):
    """Pydantic model for validating NotificationType fixture data."""

    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        roles: List[str]

    attributes: AttributesModel