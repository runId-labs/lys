from lys.apps.base.modules.access_level.services import AccessLevelService
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    """
    Fixtures for AccessLevel entities in user_role app.

    Adds ROLE access level without deleting existing ones.
    Module-qualified fixture IDs prevent conflicts with user_auth.AccessLevelFixtures.
    """

    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {
            "id": ROLE_ACCESS_LEVEL,
            "attributes": {
                "enabled": True
            }
        }
    ]