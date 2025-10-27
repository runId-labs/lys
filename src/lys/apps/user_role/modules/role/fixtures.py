from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_role.consts import USER_ADMIN_ROLE
from lys.apps.user_role.models import RoleFixturesModel
from lys.apps.user_role.modules.role.services import RoleService
from lys.core.fixtures import EntityFixtures
from lys.core.registers import register_fixture


@register_fixture()
class RoleFixtures(EntityFixtures[RoleService]):
    model = RoleFixturesModel

    data_list = [
        {
            "id": USER_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "webservices": [
                    "create_user",
                    "user"
                ]
            }
        }
    ]

    @classmethod
    async def format_webservices(cls, webservice_ids: List[str], session:AsyncSession) -> List:
        webservice_class = cls.get_entity_by_name("webservice")
        stmt = select(webservice_class).where(webservice_class.id.in_(webservice_ids))

        result = await session.execute(stmt)
        webservices: List = list(result.scalars().all())
        return webservices
