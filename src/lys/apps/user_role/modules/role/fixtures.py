from typing import List

from lys.apps.user_role.consts import USER_ADMIN_ROLE
from lys.apps.user_role.models import RoleFixturesModel
from lys.apps.user_role.modules.role.services import RoleService
from lys.core.fixtures import EntityFixtures
from lys.core.registries import register_fixture


USER_ADMIN_ROLE_WEBSERVICES = [
    "create_user",
    "user",
    "update_user_email",
    "update_password",
    "update_user_private_data",
    "update_user_status",
    "update_user_roles",
    "send_email_verification",
    "create_user_observation",
    "list_user_audit_logs",
    "all_users",
]


@register_fixture()
class RoleFixtures(EntityFixtures[RoleService]):
    model = RoleFixturesModel

    data_list = [
        {
            "id": USER_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with full user management capabilities including creating, updating, and searching users, managing roles, and viewing audit logs.",
                "role_webservices": USER_ADMIN_ROLE_WEBSERVICES
            }
        }
    ]

    @classmethod
    async def format_role_webservices(cls, webservice_ids: List[str]) -> List:
        """
        Create RoleWebservice entities for the given webservice IDs.

        Args:
            webservice_ids: List of webservice ID strings

        Returns:
            List of RoleWebservice entities (role_id will be set by SQLAlchemy relationship)
        """
        role_webservice_class = cls.app_manager.get_entity("role_webservice")
        role_webservices = []

        for ws_id in webservice_ids:
            role_webservices.append(role_webservice_class(webservice_id=ws_id))

        return role_webservices
