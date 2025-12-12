"""
Fixtures for base access level configuration.

This module provides the initial data for access levels used in the base
framework. These fixtures are loaded automatically during application startup.
"""
from lys.apps.base.modules.access_level.services import AccessLevelService
from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class AccessLevelFixtures(EntityFixtures[AccessLevelService]):
    """
    Fixtures for base AccessLevel entities.

    This fixture class provides access levels used in the base framework.

    Access Levels:
        - INTERNAL_SERVICE: Allows access for internal service-to-service communication
    """

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": INTERNAL_SERVICE_ACCESS_LEVEL,  # "INTERNAL_SERVICE"
            "attributes": {
                "enabled": True,
                "description": "Grants access for internal service-to-service communication. Use for endpoints called by other microservices."
            }
        }
    ]