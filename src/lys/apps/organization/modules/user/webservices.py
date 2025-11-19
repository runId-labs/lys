from typing import Optional

import strawberry
from sqlalchemy import Select, select, or_, exists

from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.registers import register_query
from lys.core.graphql.types import Query


@strawberry.type
@register_query()
class OrganizationUserQuery(Query):
    @lys_connection(
        UserNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,
        description="Return all users with optional organization and role filtering. Accessible to user admins."
    )
    async def all_users(
        self,
        info: Info,
        search: Optional[str] = None,
        is_client_user: Optional[bool] = None,
        role_code: Optional[str] = None
    ) -> Select:
        """
        Get all users in the system with optional search, organization, and role filtering.

        This query is accessible to users with ORGANIZATION_ROLE or ROLE access.
        Search filters by email address, first name, or last name (case-insensitive).
        Organization filtering checks if users belong to any client organization.
        Role filtering checks if users have a specific role assigned.

        Args:
            info: GraphQL context
            search: Optional search string to filter by email, first_name, or last_name
            is_client_user: Optional filter for organization membership:
                - True: users with at least one client_user relationship
                - False: users with no client_user relationships
                - None: no filtering on organization membership
            role_code: Optional role code to filter users by.
                       Returns users who have this specific role.

        Returns:
            Select: SQLAlchemy select statement for users ordered by creation date
        """
        entity_type = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")
        client_user_entity = info.context.app_manager.get_entity("client_user")

        # Base query with joins - exclude super users
        stmt = (
            select(entity_type)
            .join(email_entity)
            .join(private_data_entity)
            .where(entity_type.is_super_user.is_(False))
            .order_by(entity_type.created_at.desc())
        )

        # Apply search filter if provided
        if search:
            search_pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    email_entity.id.ilike(search_pattern),
                    private_data_entity.first_name.ilike(search_pattern),
                    private_data_entity.last_name.ilike(search_pattern)
                )
            )

        # Apply organization membership filter if provided
        if is_client_user is not None:
            # Create subquery to check if user has any client_user relationships
            client_user_exists = exists().where(
                client_user_entity.user_id == entity_type.id
            )

            if is_client_user:
                # Filter users who have at least one client_user relationship
                stmt = stmt.where(client_user_exists)
            else:
                # Filter users who have no client_user relationships
                stmt = stmt.where(~client_user_exists)

        # Apply role filter if provided
        if role_code:
            role_entity = info.context.app_manager.get_entity("role")
            # Join with roles to filter by role_code
            stmt = stmt.join(entity_type.roles).where(role_entity.id == role_code)

        return stmt