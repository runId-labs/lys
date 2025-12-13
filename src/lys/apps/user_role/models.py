from typing import List

from lys.core.models.fixtures import ParametricEntityFixturesModel


class RoleFixturesModel(ParametricEntityFixturesModel):
    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        enabled: bool
        role_webservices: List[str]

    attributes: AttributesModel