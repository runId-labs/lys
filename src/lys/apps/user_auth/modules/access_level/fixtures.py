"""
Fixtures for access level configuration data.

This module provides the initial data for access levels used throughout
the authentication system. These fixtures are loaded automatically during
application startup to ensure consistent permission levels.
"""
from lys.apps.base.modules.access_level.services import AccessLevelService
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    """
    Fixtures for AccessLevel entities.

    This fixture class provides the standard access levels used in the
    authentication system. These are loaded during application startup
    and provide the foundation for webservice access control.

    Access Levels:
        - CONNECTED: Allows access to any authenticated user
        - OWNER: Restricts access to users who own the related data

    Usage:
        These fixtures are automatically loaded by the AppManager during
        application initialization when FIXTURES is included in component_types.
    """

    # Use ParametricEntity fixture model for string ID entities
    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": CONNECTED_ACCESS_LEVEL,  # "CONNECTED"
            "attributes": {
                "enabled": True,
                "description": "Grants access to any authenticated user. Use for public data that requires login but not ownership."
            }
        },
        {
            "id": OWNER_ACCESS_LEVEL,  # "OWNER"
            "attributes": {
                "enabled": True,
                "description": "Restricts access to the user who owns the data. Use for personal or private information."
            }
        }
    ]
