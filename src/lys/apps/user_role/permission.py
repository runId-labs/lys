"""
Role-based permission system.

This module implements the permission layer for role-based access control (RBAC).
Users assigned to roles gain full access to webservices associated with those roles.
"""
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
    """
    Permission handler for role-based access control.

    This class implements RBAC where users are assigned roles, and roles are
    associated with webservices. If a user has a role that includes a webservice,
    the user gains full access to that webservice and all related data.

    Access model:
        - All-or-nothing: Users either have full access or no access
        - No row-level filtering: ROLE_ACCESS_LEVEL grants access to all data
        - Role must be enabled and include the specific webservice
    """

    @classmethod
    async def check_webservice_permission(cls, webservice: AuthWebservice, context: Context,
                                          session: AsyncSession) -> tuple[bool | Dict | None, str | None]:
        """
        Check if the connected user has permission to access the webservice through assigned roles.

        This method verifies if the user has any enabled role that includes the requested
        webservice. Role-based access is all-or-nothing: either the user has the role and
        gets full access, or they don't have the role and get no access.

        Args:
            webservice: The webservice being accessed
            context: Request context containing connected user information
            session: Database session for queries

        Returns:
            Tuple of (access_type, error_code):
            - access_type: {"role": True} if access granted, None otherwise
            - error_code: Error code string if access denied, None if access granted

        Query logic:
            Checks if there exists a webservice where:
            1. Webservice has ROLE_ACCESS_LEVEL
            2. Webservice is associated with a role
            3. Role has the connected user as a member
            4. Webservice ID matches the requested webservice
        """
        access_type: bool | Dict | None = None
        error_code: str | None = None

        connected_user = context.connected_user

        # Early return if no user is connected
        if not connected_user:
            return access_type, error_code

        # Extract enabled access levels from webservice configuration
        access_levels = [access_level.id for access_level in webservice.access_levels if access_level.enabled]

        # Check if webservice requires role-based access
        if ROLE_ACCESS_LEVEL in access_levels:
            # Retrieve entities via app_manager
            webservice_class = cls.app_manager.get_entity("webservice")
            role_class = cls.app_manager.get_entity("role")

            # Query to check if user has a role that grants access to this webservice
            # This is more efficient than loading all user roles and filtering in Python
            stmt = select(webservice_class).where(
                webservice_class.access_levels.any(id=ROLE_ACCESS_LEVEL),  # Webservice requires role access
                webservice_class.roles.any(role_class.users.any(id=connected_user["id"])),  # User has a role
                webservice_class.id == webservice.id  # Match the requested webservice
            )
            result = await session.scalars(stmt)
            user_webservice = result.one_or_none()

            # Grant full access if user has qualifying role
            if user_webservice:
                access_type = {
                    ROLE_ACCESS_KEY: True
                }

        return access_type, error_code

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        Add role-based filtering constraints to a SQLAlchemy query statement.

        For role-based access, no filtering is applied to the query because ROLE_ACCESS_LEVEL
        grants full access to all data. If the user has passed the webservice permission check,
        they can see everything.

        Args:
            stmt: The SQLAlchemy SELECT statement (returned unchanged)
            or_where: Binary expression for combining access conditions
            context: Request context containing access_type information
            entity_class: The entity class being queried (not used for role access)

        Returns:
            Tuple of (stmt, modified_or_where):
            - stmt: Unchanged statement
            - modified_or_where: OR expression with true() added (no filtering)

        Note:
            true() is a SQLAlchemy construct that represents a WHERE clause that always
            evaluates to true, effectively removing any row-level filtering.
        """
        access_type = context.access_type

        # Only apply if access_type is a dict and contains ROLE_ACCESS_KEY
        if isinstance(access_type, dict) and access_type.get(ROLE_ACCESS_KEY, False) is True:
            # Grant access to all rows without filtering
            or_where |= true()

        return stmt, or_where