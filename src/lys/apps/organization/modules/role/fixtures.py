from lys.apps.organization.consts import CLIENT_ADMIN_ROLE, CLIENT_SUPERVISOR_ROLE
from lys.apps.user_role.consts import USER_ADMIN_ROLE
from lys.apps.user_role.modules.role.fixtures import RoleFixtures
from lys.core.registries import register_fixture


USER_ADMIN_ROLE_WEBSERVICES = [
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
            "id": CLIENT_SUPERVISOR_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Supervisor role for managing all clients. Can list, view, and update any client.",
                "role_webservices": [
                    "all_clients",
                    "client",
                    "update_client"
                ],
                "supervisor_only": True
            }
        },
        {
            "id": CLIENT_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Client administrator role for managing own client. Can view and update client information.",
                "role_webservices": [
                    "client",
                    "update_client"
                ],
                "supervisor_only": False
            }
        },
        {
            "id": USER_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role for managing client users. Can create, update, and search client users within their organization.",
                "role_webservices": USER_ADMIN_ROLE_WEBSERVICES,
                "supervisor_only": False
            }
        }
    ]
