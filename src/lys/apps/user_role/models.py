from typing import List

from lys.core.models.fixtures import ParametricEntityFixturesModel


class RoleFixturesModel(ParametricEntityFixturesModel):
    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        enabled: bool
        webservices: List[str]

    attributes: AttributesModel