from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures
from lys.apps.user_role.consts import USER_ADMIN_ROLE
from lys.apps.user_role.modules.role.entities import Role
from lys.core.registers import register_fixture


@register_fixture(depends_on=["UserStatusFixtures", "RoleFixtures"])
class RoleUserDevFixtures(UserDevFixtures):
    delete_previous_data = False
    data_list = [
        {
            "attributes": {
                "email_address": "admin_user@arum-test.fr",
                "password": "password",
                "roles": [
                    USER_ADMIN_ROLE
                ]
            }
        }
    ]

    @classmethod
    async def format_roles(cls, role_id_list: List[str], session: AsyncSession = None) -> List[Role]:
        role_class = cls.get_entity_by_name("role")
        stmt = select(role_class).where(role_class.id.in_(role_id_list))
        result = await session.execute(stmt)
        roles: List[Role] = list(result.scalars().all())
        return roles
