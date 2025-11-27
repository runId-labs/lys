from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.consts import CLIENT_ADMIN_ROLE
from lys.apps.user_role.models import RoleFixturesModel
from lys.apps.user_role.modules.role.services import RoleService
from lys.core.fixtures import EntityFixtures
from lys.core.registries import register_fixture


@register_fixture()
class OrganizationRoleFixtures(EntityFixtures[RoleService]):
    model = RoleFixturesModel
    delete_previous_data: bool = False

    data_list = [
        {
            "id": CLIENT_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with client management capabilities including listing and viewing clients.",
                "webservices": [
                    "all_clients",
                    "client",
                    "update_client"
                ]
            }
        }
    ]

    @classmethod
    async def format_webservices(cls, webservice_ids: List[str], session: AsyncSession) -> List:
        webservice_class = cls.app_manager.get_entity("webservice")
        stmt = select(webservice_class).where(webservice_class.id.in_(webservice_ids))

        result = await session.execute(stmt)
        webservices: List = list(result.scalars().all())
        return webservices