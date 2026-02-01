"""
Authentication-based permission implementations.

This module provides two permission classes:
- AnonymousPermission: For non-authenticated users (no JWT), checks registry for public_type
- JWTPermission: For authenticated users, checks JWT claims for webservice access
"""
from typing import Type, Tuple, Optional, Dict, Union, Any

from sqlalchemy import Select, BinaryExpression, or_

from lys.apps.user_auth.consts import OWNER_ACCESS_KEY
from lys.apps.user_auth.errors import ACCESS_DENIED_ERROR
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface


class AnonymousPermission(PermissionInterface):
    """
    Permission handler for anonymous (non-authenticated) users.

    This class handles access for users without a JWT token.
    It checks if the webservice is marked as public via the registry config.

    Used by: All servers (stateless check via registry)
    """

    @classmethod
    async def check_webservice_permission(cls, webservice_id: str,
                                          context: Context) -> tuple[bool | Dict | None, str | None]:
        """
        Check if anonymous user can access a public webservice.

        Only grants access if:
        - User is not connected (no JWT)
        - Webservice has public_type set in registry config

        Args:
            webservice_id: The webservice identifier
            context: Request context containing app_manager

        Returns:
            Tuple of (access_type, error_code):
            - (True, None) if public webservice and user not connected
            - (None, None) if user is connected (let other permissions handle it)
            - (None, ACCESS_DENIED_ERROR) if not public and not connected
        """
        # If user is connected, let JWTPermission handle it
        if context.connected_user is not None:
            return None, None

        # Anonymous user - check if webservice is public via registry
        webservice_config = context.app_manager.registry.webservices.get(webservice_id, {})
        public_type = webservice_config.get("attributes", {}).get("public_type")

        if public_type is not None:
            return True, None

        # Not public and not connected - access denied
        return None, ACCESS_DENIED_ERROR

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        No filtering for anonymous access to public webservices.

        Public webservices grant full read access without row-level filtering.
        """
        return stmt, or_where


class JWTPermission(PermissionInterface):
    """
    Permission handler for authenticated users using JWT claims.

    This class checks if the webservice name is present in the user's
    JWT 'webservices' claim. No database queries are performed.

    The webservices claim is a dict mapping webservice name to access type:
    - "full": Full access to all data
    - "owner": Access only to data owned by the user

    Used by: All microservices (stateless JWT verification)
    """

    @classmethod
    async def check_webservice_permission(cls, webservice_id: str,
                                          context: Context) -> tuple[bool | Dict | None, str | None]:
        """
        Check if authenticated user can access webservice via JWT claims.

        Grants access if:
        - User is a super user (full access)
        - Webservice name is in user's JWT 'webservices' claim

        Args:
            webservice_id: The webservice identifier
            context: Request context containing JWT claims

        Returns:
            Tuple of (access_type, error_code):
            - (True, None) for full access
            - ({OWNER_ACCESS_KEY: True}, None) for owner-filtered access
            - (None, None) if not in claims (let other permissions handle it)
        """
        connected_user = context.connected_user

        # If not connected, let AnonymousPermission handle it
        if connected_user is None:
            return None, None

        # Super user bypass - full access to everything
        if connected_user.get("is_super_user", False):
            return True, None

        # Check if webservice is in JWT claims
        user_webservices = connected_user.get("webservices", {})

        if webservice_id in user_webservices:
            access_type = user_webservices[webservice_id]

            if access_type == "owner":
                return {OWNER_ACCESS_KEY: True}, None

            # "full" access
            return True, None

        # Not in claims - no access from this permission
        return None, None

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        Add owner-based filtering constraints for OWNER access level.

        When access_type contains OWNER_ACCESS_KEY, filters queries to only
        return entities owned by the connected user.

        Args:
            stmt: The SQLAlchemy SELECT statement to modify
            or_where: Binary expression for combining access conditions
            context: Request context containing access_type
            entity_class: Entity class (must implement user_accessing_filters)

        Returns:
            Tuple of (modified_stmt, modified_or_where)
        """
        access_type: Union[Dict[str, Any], bool] = context.access_type
        connected_user_id: str | None = context.connected_user.get('sub') if context.connected_user else None

        # Only apply owner filtering if access_type is a dict with OWNER_ACCESS_KEY
        if isinstance(access_type, dict) and access_type.get(OWNER_ACCESS_KEY, False):
            if len(stmt.get_final_froms()) and entity_class is not None and connected_user_id:
                stmt, conditions = entity_class.user_accessing_filters(stmt, connected_user_id)
                if conditions:
                    or_where |= or_(*conditions)

        return stmt, or_where


# Backward compatibility alias
UserAuthPermission = JWTPermission