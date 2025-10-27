from typing import List

from pydantic import Field

from lys.core.models.fixtures import ParametricEntityFixturesModel


class WebserviceFixturesModel(ParametricEntityFixturesModel):
    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        public_type: str | None = Field(..., min_length=1)
        is_licenced: bool
        enabled: bool
        access_levels: List[str]

    id: str = Field(..., min_length=1)
    attributes: AttributesModel