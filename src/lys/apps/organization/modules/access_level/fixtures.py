from lys.apps.base.modules.access_level.services import AccessLevelService
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    """
    Fixtures for AccessLevel entities in organization app.

    Adds ORGANIZATION_ROLE access level without deleting existing ones.
    Module-qualified fixture IDs prevent conflicts with other AccessLevelFixtures.
    """

    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {
            "id": ORGANIZATION_ROLE_ACCESS_LEVEL,
            "attributes": {
                "enabled": True
            }
        }
    ]