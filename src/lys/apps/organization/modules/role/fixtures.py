from lys.apps.organization.consts import CLIENT_ADMIN_ROLE
from lys.apps.user_role.consts import USER_ADMIN_ROLE
from lys.apps.user_role.modules.role.fixtures import USER_ADMIN_ROLE_WEBSERVICES, RoleFixtures
from lys.core.registries import register_fixture


USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES = USER_ADMIN_ROLE_WEBSERVICES + [
    "all_clients",
    "all_client_users",
    "client_user",
    "create_client_user",
    "update_client_user_email",
    "update_client_user_private_data",
    "update_client_user_roles",
]


@register_fixture()
class OrganizationRoleFixtures(RoleFixtures):
    data_list = [
        {
            "id": CLIENT_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with client management capabilities including listing and viewing clients.",
                "role_webservices": [
                    "all_clients",
                    "client",
                    "update_client"
                ]
            }
        },
        {
            "id": USER_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with full user management capabilities including creating, updating, and searching users, managing roles, and viewing audit logs.",
                "role_webservices": USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES
            }
        }
    ]
