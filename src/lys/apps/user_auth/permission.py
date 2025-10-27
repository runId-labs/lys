"""
Authentication-based permission implementation.

This module implements the permission interface with business logic specific
to the authentication system. It handles webservice access control based on
user authentication state, webservice configuration, and access levels.
"""
from typing import Type, Tuple, Optional, Dict, Union, Any

from sqlalchemy import Select, BinaryExpression, or_
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.consts import OWNER_ACCESS_KEY
from lys.apps.user_auth.errors import ALREADY_CONNECTED_ERROR, ACCESS_DENIED_ERROR
from lys.apps.user_auth.modules.webservice.entities import AuthWebservice
from lys.core.consts.webservices import DISCONNECTED_WEBSERVICE_PUBLIC_TYPE, CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface


class UserAuthPermission(PermissionInterface):
    """
    Authentication-based permission implementation.

    This class implements the PermissionInterface with comprehensive business
    logic for webservice access control. It considers multiple factors:
    - User authentication state (connected/disconnected)
    - Webservice public access configuration
    - User privileges (super user status)
    - Access level requirements (CONNECTED, OWNER)

    The permission system supports:
    - Public webservices (with optional restrictions)
    - Private webservices (authentication required)
    - Owner-based access control (row-level security)
    - Super user bypass for administrative access
    """

    @classmethod
    async def check_webservice_permission(cls, webservice: AuthWebservice, context: Context,
                                          session: AsyncSession) -> tuple[bool | Dict | None, str | None]:
        access_type: bool | Dict | None = None
        error_code: str | None = None

        if webservice.is_public:
            if webservice.public_type_id == DISCONNECTED_WEBSERVICE_PUBLIC_TYPE and context.connected_user is not None:
                error_code = ALREADY_CONNECTED_ERROR
            else:
                access_type = True
        elif context.connected_user is None:
            error_code = ACCESS_DENIED_ERROR
        elif context.connected_user.get('is_super_user', False):
            # if user is a superuser, he has access to any webservice
            access_type = True
        else:
            # get webservice enabled access levels
            access_levels = [access_level.id for access_level in webservice.access_levels if access_level.enabled]

            # CONNECTED_ACCESS_LEVEL or ROLE_ACCESS_LEVEL are full data access
            if CONNECTED_ACCESS_LEVEL in access_levels:
                # CONNECTED_ACCESS_LEVEL = you just need to be connected to access to the webservice
                access_type = True
            elif OWNER_ACCESS_LEVEL in access_levels:
                # owner as user
                # True because the access is defined after on the entity or in the query filters
                access_type = {OWNER_ACCESS_KEY: True}

        if error_code is not None:
            access_type = False

        return access_type, error_code

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:

        access_type: Union[Dict[str, Any], bool] = context.access_type
        connected_user_id: str | None = context.connected_user.get('id') if context.connected_user is not None else None

        if isinstance(access_type, dict):
            if len(stmt.froms):
                if entity_class is not None:
                    if connected_user_id and access_type.get(OWNER_ACCESS_LEVEL, False):
                        stmt, conditions = entity_class.user_accessing_filters(stmt, connected_user_id)
                        if len(conditions):
                            or_where |= or_(*conditions)
                else:
                    raise ValueError(
                        "Entity type is required"
                    )

        return stmt, or_where