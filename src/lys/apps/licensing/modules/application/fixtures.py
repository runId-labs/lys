"""
Fixtures for license application definitions.

Defines the default application for single-app deployments.
Additional applications can be added for multi-app deployments.
"""

from lys.apps.licensing.consts import DEFAULT_APPLICATION
from lys.apps.licensing.modules.application.services import LicenseApplicationService
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class LicenseApplicationDevFixtures(EntityFixtures[LicenseApplicationService]):
    """
    Fixtures for license application definitions.

    The DEFAULT application is used for single-app deployments.
    Multi-app deployments can add additional applications.
    """
    model = ParametricEntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV]

    data_list = [
        {
            "id": DEFAULT_APPLICATION,
            "attributes": {
                "enabled": True,
                "description": "Default application"
            }
        },
    ]