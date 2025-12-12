"""
Organization-based permission system using JWT claims.

This module implements the permission layer for organization-scoped access control.
Permission checking uses JWT claims instead of database queries for stateless
verification in microservices architecture.
"""
from typing import Type, Tuple, Optional, Dict

from sqlalchemy import Select, BinaryExpression, or_

from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY
from lys.core.contexts import Context
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.permissions import PermissionInterface


class OrganizationPermission(PermissionInterface):
    """
    Permission handler for organization-based access control using JWT claims.

    This class checks if the webservice name is present in any of the user's
    organization claims (from JWT 'organizations' dict). No database queries
    are performed.

    JWT organizations structure:
    {
        "organizations": {
            "client-uuid-1": {
                "level": "client",
                "webservices": ["manage_billing", "list_projects"]
            }
        }
    }

    Access type structure when granted:
    {
        "organization_role": {
            "client": [client_id1, client_id2, ...]
        }
    }
    """

    @classmethod
    async def check_webservice_permission(cls, webservice_id: str,
                                          context: Context) -> tuple[bool | Dict | None, str | None]:
        """
        Check if user has permission via organization claims in JWT.

        Grants access if the webservice name is present in any organization's
        webservices list from the JWT claims.

        Args:
            webservice_id: The webservice identifier
            context: Request context containing JWT claims

        Returns:
            Tuple of (access_type, error_code):
            - access_type: Dict with organization IDs if granted, None otherwise
            - error_code: Always None (errors handled elsewhere)
        """
        access_type: bool | Dict | None = None
        error_code: str | None = None

        connected_user = context.connected_user

        # If not connected, skip
        if connected_user is None:
            return None, None

        # Get organizations from JWT claims
        organizations = connected_user.get("organizations", {})

        if not organizations:
            return None, None

        # Find organizations that grant access to this webservice
        accessible_orgs = {}

        for org_id, org_data in organizations.items():
            org_level = org_data.get("level", "client")
            org_webservices = org_data.get("webservices", [])

            if webservice_id in org_webservices:
                # Initialize level list if needed
                if org_level not in accessible_orgs:
                    accessible_orgs[org_level] = []
                accessible_orgs[org_level].append(org_id)

        # If user has access via any organization, build access_type
        if accessible_orgs:
            access_type = {
                ORGANIZATION_ROLE_ACCESS_KEY: accessible_orgs
            }

        return access_type, error_code

    @classmethod
    async def add_statement_access_constraints(cls, stmt: Select, or_where: BinaryExpression, context,
                                               entity_class: Optional[Type[EntityInterface]]
                                               ) -> Tuple[Select, BinaryExpression]:
        """
        Add organization-based filtering constraints to a SQLAlchemy query statement.

        Filters queries to only return entities belonging to organizations
        where the user has access (from JWT claims).

        Args:
            stmt: The SQLAlchemy SELECT statement to modify
            or_where: Binary expression for combining access conditions
            context: Request context containing access_type
            entity_class: Entity class (must implement organization_accessing_filters)

        Returns:
            Tuple of (modified_stmt, modified_or_where)
        """
        access_type = context.access_type

        # Only apply constraints if access_type is a dict with organization info
        if isinstance(access_type, dict):
            if len(stmt.froms) and entity_class is not None:
                accessing_organization_dict = access_type.get(ORGANIZATION_ROLE_ACCESS_KEY)

                if accessing_organization_dict:
                    stmt, conditions = entity_class.organization_accessing_filters(
                        stmt, accessing_organization_dict
                    )
                    if conditions:
                        or_where |= or_(*conditions)

        return stmt, or_where