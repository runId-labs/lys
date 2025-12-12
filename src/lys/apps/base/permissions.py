from typing import Dict, Optional, Type, Tuple

from sqlalchemy import Select, BinaryExpression

from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface


class BasePermission(PermissionInterface):
    """Class for checking permissions on webservice. This one allows all webservices.
    Use it only if you don't need other permission like auth permission."""
    @classmethod
    async def check_webservice_permission(cls, webservice_id: str,
                                          context: Context) -> tuple[bool | Dict | None, str | None]:
        # this permission is always allowed webservice
        return True, None

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_type: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        # fonction add no contrains on webservices
        return stmt, or_where


class InternalServicePermission(PermissionInterface):
    """
    Permission handler for internal service-to-service communication.

    This class handles access for internal services authenticated via
    service JWT tokens. It grants access if:
    - The webservice has INTERNAL_SERVICE access level configured (via registry)
    - The request contains a valid service_caller (set by ServiceAuthMiddleware)

    Used by: Internal microservices communicating with each other
    """

    @classmethod
    async def check_webservice_permission(cls, webservice_id: str,
                                          context: Context) -> tuple[bool | Dict | None, str | None]:
        """
        Check if internal service can access the webservice.

        Grants access if:
        - Webservice has INTERNAL_SERVICE access level (checked via registry)
        - Request has valid service_caller from ServiceAuthMiddleware

        Args:
            webservice_id: The webservice identifier
            context: Request context containing service_caller and app_manager

        Returns:
            Tuple of (access_type, error_code):
            - (True, None) if service is authenticated and webservice allows internal access
            - (None, None) otherwise (let other permissions handle it)
        """
        service_caller = context.service_caller

        # If no service caller, let other permissions handle it
        if service_caller is None:
            return None, None

        # Check if webservice allows internal service access via registry config
        webservice_config = context.app_manager.registry.webservices.get(webservice_id, {})
        access_levels = webservice_config.get("attributes", {}).get("access_levels", [])

        if INTERNAL_SERVICE_ACCESS_LEVEL not in access_levels:
            return None, None

        # Service authenticated and webservice allows internal access
        return True, None

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_type: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        No row-level filtering for internal service access.

        Internal services have full access to data without row-level restrictions.
        """
        return stmt, or_where