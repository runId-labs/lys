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
        """
        Add owner-based filtering constraints to a SQLAlchemy query statement.

        This method modifies database queries to enforce row-level security based on
        ownership. When OWNER_ACCESS_LEVEL is configured, users can only access entities
        they own (where user_id matches the connected user's ID).

        Args:
            stmt: The SQLAlchemy SELECT statement to modify
            or_where: Binary expression for combining multiple access conditions with OR
            context: Request context containing access_type and connected_user information
            entity_class: The entity class being queried (must implement user_accessing_filters)

        Returns:
            Tuple of (modified_stmt, modified_or_where):
            - modified_stmt: Statement with any necessary joins added
            - modified_or_where: OR expression with owner filters added

        Raises:
            ValueError: If entity_class is None when access_type requires filtering
        """
        access_type: Union[Dict[str, Any], bool] = context.access_type
        connected_user_id: str | None = context.connected_user.get('id') if context.connected_user is not None else None

        # Only apply constraints if access_type is a dict (contains specific access rules)
        # If access_type is True, no filtering is needed (full access granted)
        if isinstance(access_type, dict):
            # Only apply filters if the statement has FROM clauses (is a real query)
            if len(stmt.froms):
                if entity_class is not None:
                    # Check if OWNER_ACCESS_LEVEL is configured and user is connected
                    if connected_user_id and access_type.get(OWNER_ACCESS_KEY, False):
                        # Delegate to entity-specific filtering logic
                        # Each entity knows how to filter by ownership (typically user_id column)
                        stmt, conditions = entity_class.user_accessing_filters(stmt, connected_user_id)
                        if conditions:
                            or_where |= or_(*conditions)
                else:
                    # If we need to filter but don't have an entity class, this is a configuration error
                    raise ValueError(
                        "Entity type is required for owner-based access filtering"
                    )

        return stmt, or_where