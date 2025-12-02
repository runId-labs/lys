"""
Role fixtures for licensing app.

Defines the LICENSE_ADMIN_ROLE with access to subscription management webservices.
"""

from lys.apps.licensing.consts import LICENSE_ADMIN_ROLE
from lys.apps.user_role.modules.role.fixtures import RoleFixtures
from lys.core.registries import register_fixture


LICENSE_ADMIN_ROLE_WEBSERVICES = [
    "all_clients",
    "subscription",
]


@register_fixture()
class LicensingRoleFixtures(RoleFixtures):
    """
    Fixtures for licensing-specific roles.

    Adds LICENSE_ADMIN_ROLE without deleting existing roles.
    """

    delete_previous_data = False

    data_list = [
        {
            "id": LICENSE_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with license and subscription management capabilities.",
                "webservices": LICENSE_ADMIN_ROLE_WEBSERVICES
            }
        }
    ]