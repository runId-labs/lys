"""
Organization-based permission system.

This module implements the permission layer for organization-scoped access control.
It handles checking webservice access based on organization roles and filtering
database queries to respect organization boundaries.
"""
from typing import Type, Tuple, Optional, Dict

from sqlalchemy import Select, BinaryExpression, or_
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.organization.modules.user.services import UserService
from lys.apps.user_auth.modules.webservice.entities import AuthWebservice
from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface
from lys.core.utils.manager import AppManagerCallerMixin


class OrganizationPermission(PermissionInterface, AppManagerCallerMixin):
    """
    Permission handler for organization-based access control.

    This class implements organization-scoped permissions where users gain access
    to resources through roles assigned within specific organizations. Access is
    limited to entities belonging to organizations where the user has an active role.

    Access type structure when granted:
    {
        "organization_role": {
            "client": [client_id1, client_id2, ...],
            "department": [dept_id1, dept_id2, ...],
            ...
        }
    }
    """
    @classmethod
    async def check_webservice_permission(cls, webservice: AuthWebservice, context: Context,
                                          session: AsyncSession) -> tuple[bool | Dict | None, str | None]:
        """
        Check if the connected user has permission to access the webservice through organization roles.

        This method determines webservice access by checking if the user has any active roles
        in organizations that grant access to the requested webservice. Access is granted on a
        per-organization basis, meaning users can access data only within organizations where
        they have appropriate roles.

        Args:
            webservice: The webservice being accessed
            context: Request context containing connected user information
            session: Database session for queries

        Returns:
            Tuple of (access_type, error_code):
            - access_type: Dict mapping organizations to accessible IDs if granted, None otherwise
            - error_code: Error code string if access denied, None if access granted

        Access type structure:
            {
                "organization_role": {
                    "client": [client_id1, client_id2],
                    "department": [dept_id1],
                    ...
                }
            }
        """
        access_type: bool | Dict | None = None
        error_code: str | None = None

        # Get user service to query organization roles
        user_service: type[UserService] = cls.app_manager.get_service("user")

        connected_user = context.connected_user

        # Extract enabled access levels from webservice configuration
        access_levels = [access_level.id for access_level in webservice.access_levels if access_level.enabled]

        # Check if webservice requires organization role access
        if ORGANIZATION_ROLE_ACCESS_LEVEL in access_levels:
            # TODO: Add license checking logic here
            # This would verify if the user's organization has an active license
            # that permits access to this webservice
            has_permission = True

            if has_permission:
                # Query all organization roles that grant access to this webservice
                # This returns roles where:
                # 1. User is a member of the organization through client_user
                # 2. Role is enabled
                # 3. Role includes this specific webservice (if webservice_id provided)
                user_organization_roles = await user_service.get_user_organization_roles(
                    connected_user["id"],
                    session,
                    webservice_id=webservice.id,
                )

                # Build access map if user has any qualifying roles
                if user_organization_roles:
                    # Initialize access type structure
                    access_type = {}

                    # Process each role to extract organization access
                    for user_organization_role in user_organization_roles:
                        # NOTE: This loop cannot be optimized into a single query because
                        # organization entities are polymorphic and stored across multiple tables
                        # (e.g., client, department, division, etc.)

                        # Initialize organization_role key if first iteration
                        if ORGANIZATION_ROLE_ACCESS_KEY not in access_type:
                            access_type[ORGANIZATION_ROLE_ACCESS_KEY] = {}

                        # Extract organization from the role relationship
                        organization = user_organization_role.organization
                        organization_model_name = str(organization.__tablename__)

                        # Initialize list for this organization type if needed
                        if organization_model_name not in access_type[ORGANIZATION_ROLE_ACCESS_KEY]:
                            access_type[ORGANIZATION_ROLE_ACCESS_KEY][organization_model_name] = []

                        # Add organization ID to accessible organizations
                        # This allows filtering queries to only return data belonging to these organizations
                        access_type[ORGANIZATION_ROLE_ACCESS_KEY][organization_model_name].append(
                            organization.id
                        )

        return access_type, error_code

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        Add organization-based filtering constraints to a SQLAlchemy query statement.

        This method modifies database queries to enforce organization-level access control.
        It adds WHERE clauses that restrict results to only include entities belonging to
        organizations where the user has appropriate roles.

        The filtering logic is delegated to each entity's `organization_accessing_filters`
        method, which knows how to join and filter based on that entity's specific
        relationship to organizations.

        Args:
            stmt: The SQLAlchemy SELECT statement to modify
            or_where: Binary expression for combining multiple access conditions with OR
            context: Request context containing access_type information
            entity_class: The entity class being queried (must implement organization_accessing_filters)

        Returns:
            Tuple of (modified_stmt, modified_or_where):
            - modified_stmt: Statement with any necessary joins added
            - modified_or_where: OR expression with organization filters added

        Raises:
            ValueError: If entity_class is None when access_type requires filtering

        Example:
            User has access to client_id=1 and client_id=2.
            Query for projects will be filtered to only return projects
            where project.client_id IN (1, 2).
        """
        access_type = context.access_type

        # Only apply constraints if access_type is a dict (contains specific access rules)
        # If access_type is True, no filtering is needed (full access)
        # If access_type is None/False, access is denied at the webservice level
        if isinstance(access_type, dict):
            # Only apply filters if the statement has FROM clauses (is a real query)
            if len(stmt.froms):
                if entity_class is not None:
                    # Extract organization access information from access_type
                    # Structure: {"organization_role": {"client": [id1, id2], "department": [id3]}}
                    accessing_organization_dict = access_type.get(ORGANIZATION_ROLE_ACCESS_KEY)

                    if accessing_organization_dict:
                        # Delegate to entity-specific filtering logic
                        # Each entity knows how to filter based on its organization relationships
                        # Returns modified statement (with joins if needed) and list of filter conditions
                        stmt, conditions = entity_class.organization_accessing_filters(stmt, accessing_organization_dict)

                        # Add organization filter conditions to the OR expression
                        # Multiple conditions are combined with OR to allow access to entities
                        # from any of the user's accessible organizations
                        if conditions:
                            or_where |= or_(*conditions)
                else:
                    # If we need to filter but don't have an entity class, this is a configuration error
                    raise ValueError(
                        "Entity type is required for organization-based access filtering"
                    )

        return stmt, or_where