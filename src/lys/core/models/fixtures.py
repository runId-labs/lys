from pydantic import BaseModel, Field

from lys.core.models.entities import EntityModel


class EntityFixturesModel(EntityModel):
    class AttributesModel(BaseModel):
        __hash__ = object.__hash__

    attributes: AttributesModel = None


class ParametricEntityFixturesModel(EntityFixturesModel):
    class AttributesModel(EntityFixturesModel.AttributesModel):
        enabled: bool | None = None
        description: str | None = None

    attributes: AttributesModel | dict = dict()

    id: str = Field(..., min_length=1)