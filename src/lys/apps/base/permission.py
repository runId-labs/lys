from typing import Dict, Optional, Type, Tuple

from sqlalchemy import Select, BinaryExpression
from sqlalchemy.ext.asyncio import AsyncSession

from lys.core.abstracts.webservices import AbstractWebservice
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface


class BasePermission(PermissionInterface):
    """Class for checking permissions on webservice. This one allows all webservices.
    Use it only if you don't need other permission like auth permission."""
    @classmethod
    async def check_webservice_permission(cls, webservice: AbstractWebservice, context,
                                          session: AsyncSession) -> tuple[bool | Dict | None, str | None]:
        # this permission is always allowed webservice
        return True, None

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_type: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        # fonction add no contrains on webservices
        return stmt, or_where