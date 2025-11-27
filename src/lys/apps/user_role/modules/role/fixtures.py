from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_role.consts import USER_ADMIN_ROLE
from lys.apps.user_role.models import RoleFixturesModel
from lys.apps.user_role.modules.role.services import RoleService
from lys.core.fixtures import EntityFixtures
from lys.core.registries import register_fixture


@register_fixture()
class RoleFixtures(EntityFixtures[RoleService]):
    model = RoleFixturesModel

    data_list = [
        {
            "id": USER_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with full user management capabilities including creating, updating, and searching users, managing roles, and viewing audit logs.",
                "webservices": [
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
                    "all_roles",
                    "all_users",
                    "all_client_users",
                    "client_user",
                    "update_client_user_email",
                    "update_client_user_private_data",
                    "update_client_user_roles"
                ]
            }
        }
    ]

    @classmethod
    async def format_webservices(cls, webservice_ids: List[str], session:AsyncSession) -> List:
        webservice_class = cls.app_manager.get_entity("webservice")
        stmt = select(webservice_class).where(webservice_class.id.in_(webservice_ids))

        result = await session.execute(stmt)
        webservices: List = list(result.scalars().all())
        return webservices
