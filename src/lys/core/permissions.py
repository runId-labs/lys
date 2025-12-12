"""
GraphQL permissions utilities for webservice-based authorization.

This module provides factory functions and utilities for creating Strawberry GraphQL
permission classes that integrate with the lys pluggable permission system.

Key Components:
    - get_access_type(): Core permission computation logic
    - generate_webservice_permission(): Factory for GraphQL permission classes

Architecture:
    The permission system uses a pluggable approach where multiple permission modules
    can be loaded and executed in sequence. Boolean results provide final decisions,
    while dict results allow complex permission metadata to be merged.
"""
import logging
import traceback
from typing import Any, Optional

from sqlalchemy import Select, false
from strawberry import BasePermission

from lys.core.consts.errors import PERMISSION_DENIED_ERROR, UNKNOWN_WEBSERVICE_ERROR
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.managers.app import AppManager
from lys.core.utils.manager import AppManagerCallerMixin


async def get_access_type(app_manager, webservice_id: str,
                          context: Context) -> tuple[dict | bool, tuple[int, str]]:
    """
    Compute access permissions for a webservice using the pluggable permission system.

    This function implements the core authorization logic by:
    1. Iterating through all registered permission modules in order
    2. Allowing each module to grant/deny access or provide access metadata
    3. Merging dictionary-based access types for complex permissions
    4. Returning the first boolean decision or final merged result

    Args:
        app_manager: AppManager instance containing loaded permission modules
        webservice_id: Target webservice identifier to check permissions for
        context: Request context containing user and session data

    Returns:
        tuple: (access_type, error_tuple) where:
            - access_type: bool (granted/denied) or dict (complex permissions)
            - error_tuple: (error_code, error_message) for client responses

    Business Logic:
        - Unknown/disabled webservice → UNKNOWN_WEBSERVICE_ERROR
        - Boolean permission result → immediate return (first wins)
        - Dict permission results → merged for complex access patterns
    """
    access_type: dict | bool = False
    message_tuple: tuple[int, str] = PERMISSION_DENIED_ERROR

    # Check webservice config from registry
    webservice_config = app_manager.registry.webservices.get(webservice_id, {})
    webservice_enabled = webservice_config.get("attributes", {}).get("enabled", False)

    # Early validation: disabled/missing webservices are inaccessible
    if not webservice_config or not webservice_enabled:
        message_tuple = UNKNOWN_WEBSERVICE_ERROR
    else:
        # Execute permission chain: each module can grant, deny, or provide metadata
        # Order matters - first boolean result wins, dicts get merged
        for permission in app_manager.permissions:
            try:
                computed_access_type, computed_message_tuple = \
                    await permission.check_webservice_permission(webservice_id, context)

                # Boolean results are final decisions (grant/deny)
                if isinstance(computed_access_type, bool):
                    access_type = computed_access_type
                    if computed_message_tuple is not None:
                        message_tuple = computed_message_tuple
                    break

                # Dictionary results contain access metadata (roles, levels, etc.)
                elif isinstance(computed_access_type, dict):
                    # Replace initial False with first dict permission
                    if access_type is False:
                        access_type = computed_access_type
                    # Merge with existing dict permissions (additive permissions)
                    elif isinstance(access_type, dict):
                        access_type = {**access_type, **computed_access_type}

            except Exception as e:
                # Log permission module error but continue with other modules
                logging.error(f"Permission module {permission.__class__.__name__} failed: {e}")
                # Continue to the next permission module (resilient permission chain)

    return access_type, message_tuple


def generate_webservice_permission(
        webservice_id: str
) -> type[BasePermission]:
    """
    Factory function that creates GraphQL permission classes for specific webservices.

    This implements the factory pattern to generate Strawberry GraphQL permission
    decorators that are bound to specific webservice IDs. Each generated class
    handles the complete authorization flow including user initialization,
    permission checking, and context updates.

    Architecture Benefits:
        - One permission class per webservice (isolation)
        - Automatic user context initialization
        - Seamless integration with Strawberry GraphQL
        - Pluggable permission system via app_manager.permissions

    Usage in GraphQL:
        @strawberry.field(permission_classes=[generate_webservice_permission(app, "api_v1")])
        def my_resolver(self, info) -> MyType:
            # Permission already checked, context.access_type populated

    Args:
        webservice_id: Unique identifier for the target webservice

    Returns:
        WebservicePermission class ready for Strawberry GraphQL decoration

    Implementation Notes:
        - Uses closure to capture app_manager and webservice_id
        - Mutates context.access_type for downstream resolvers
        - Integrates with lys permission interface contract
    """
    class WebservicePermission(AppManagerCallerMixin, BasePermission):
        """Strawberry GraphQL permission class for webservice-specific authorization."""

        code = PERMISSION_DENIED_ERROR
        message = PERMISSION_DENIED_ERROR[1]

        async def has_permission(self, source: Any, info, **kwargs) -> bool:
            """Strawberry GraphQL permission entry point."""
            context = info.context
            return await self.has_routers_permission(context)

        async def has_routers_permission(self, context) -> bool:
            """
            Core authorization logic for webservice access with explicit error handling.

            Flow:
            1. Check webservice configuration from registry
            2. Execute the permission chain via get_access_type()
            3. Update context with computed access_type for resolvers
            4. Return boolean decision for GraphQL framework

            Error Handling:
                - Unknown webservice → UNKNOWN_WEBSERVICE_ERROR
                - Permission failures → PERMISSION_DENIED_ERROR
                - All errors logged for debugging, access denied for security

            Side Effects:
                - Populates context.access_type for downstream use
                - Updates self.code/self.message for error responses
            """
            try:
                # Execute the pluggable permission system
                access_type, (self.code, self.message) = await get_access_type(
                    self.app_manager, webservice_id, context
                )

                # Populate context for downstream GraphQL resolvers
                context.access_type = access_type

                # Convert to boolean for the Strawberry GraphQL framework
                return bool(access_type)

            except Exception as e:
                # Fallback: deny access but log for debugging
                logging.error(f"Permission check failed for webservice {webservice_id}: {e}")
                traceback.print_exc()
                self.code, self.message = PERMISSION_DENIED_ERROR
                return False

    return WebservicePermission


async def add_access_constraints(
        stmt: Select,
        context: Context,
        entity_class: Optional[type[EntityInterface]],
        app_manager: AppManager,
):
    """
    Add access conditions to secure the query
    :param stmt:
    :param context:
    :param entity_class:
    :param app_manager:
    :return:
    """
    access_type = context.access_type

    # if no access, return nothing
    if access_type is False:
        stmt = stmt.where(false())
    # access_type is a dictionary
    elif isinstance(access_type, dict):
        or_where = false()

        # check all permission
        for permission in app_manager.permissions:
            stmt, or_where = await permission.add_statement_access_constraints(stmt, or_where, context, entity_class)

        stmt = stmt.where(or_where)

    return stmt