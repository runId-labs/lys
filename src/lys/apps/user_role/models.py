from typing import List

from lys.core.models.fixtures import ParametricEntityFixturesModel


class RoleFixturesModel(ParametricEntityFixturesModel):
    class AttributesModel(ParametricEntityFixturesModel.AttributesModel):
        enabled: bool
        role_webservices: List[str]
        supervisor_only: bool = False

    attributes: AttributesModel