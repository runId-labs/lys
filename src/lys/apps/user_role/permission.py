from typing import Type, Tuple, Optional, Dict

from sqlalchemy import Select, BinaryExpression, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.webservice.entities import AuthWebservice
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.consts.permissions import ROLE_ACCESS_KEY
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface
from lys.core.utils.manager import AppManagerCallerMixin


class UserRolePermission(PermissionInterface, AppManagerCallerMixin):
    @classmethod
    async def check_webservice_permission(cls, webservice: AuthWebservice, context: Context,
                                          session: AsyncSession) -> tuple[bool | Dict | None, str | None]:
        access_type: bool | Dict | None = None
        error_code: str | None = None

        connected_user = context.connected_user
        # get webservice enabled access levels
        access_levels = [access_level.id for access_level in webservice.access_levels if access_level.enabled]

        if ROLE_ACCESS_LEVEL in access_levels:
            # check if the webservice in the user role accessed webservices
            webservice_class= cls.app_manager.register.get_entity("webservice")
            role_class = cls.app_manager.register.get_entity("role")



            stmt = select(webservice_class).where(
                webservice_class.access_levels.any(id=ROLE_ACCESS_LEVEL),
                webservice_class.roles.any(role_class.users.any(id=connected_user.id)),
                webservice_class.id == webservice.id
            )
            result = await session.scalars(stmt)
            user_webservice = result.one_or_none()

            # if yes, user has full access to the webservice by role
            if user_webservice:
                access_type = {
                    ROLE_ACCESS_KEY: True
                }

        return access_type, error_code

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:

        access_type = context.access_type

        if access_type.get(ROLE_ACCESS_KEY, False) is True:
            # return everything without constraint
            or_where |= true()

        return stmt, or_where