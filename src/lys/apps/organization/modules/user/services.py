from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity
from lys.apps.organization.modules.client.entities import ClientUserRole
from lys.apps.user_role.modules.user.services import UserService as UserRoleService
from lys.core.registers import register_service


@register_service()
class UserService(UserRoleService):
    @classmethod
    async def get_user_organization_roles(
        cls,
        user_id: str,
        session: AsyncSession,
        webservice_id: str = None
    ) -> list[AbstractUserOrganizationRoleEntity]:
        """
        Retrieve all organization roles assigned to a user with optimized eager loading.

        This method queries the database to find all active roles that a user has
        within organizations. It uses eager loading to avoid N+1 query problems
        when accessing related organization data.

        The method follows this relationship chain:
        User → ClientUser → ClientUserRole → Role (with webservice filter)

        Performance optimization:
            Uses selectinload() to eagerly load:
            - ClientUserRole.client_user → ClientUser
            - ClientUser.client → Client
            This prevents N+1 queries when accessing user_organization_role.organization

        Args:
            user_id: The ID of the user to query roles for
            session: Database session for executing the query
            webservice_id: Optional webservice ID to filter roles that include this webservice

        Returns:
            List of ClientUserRole entities with preloaded organization relationships

        Query details:
            - Joins ClientUserRole with ClientUser to access user_id
            - Joins ClientUserRole with Role to check enabled status and webservices
            - Filters by user_id to get only roles for this user
            - Filters by role.enabled=True to exclude disabled roles
            - Optionally filters by webservice_id if provided
            - Eagerly loads client_user and client relationships

        Performance:
            Without optimization: 1 + (N × 2) queries for N roles
            With optimization: 3 queries total (main + 2 selectinload batches)

        Note:
            Currently only supports ClientUserRole. Future implementations may need to
            support additional organization types (e.g., DepartmentUserRole, DivisionUserRole).
        """
        # Retrieve entities from app_manager (following framework pattern)
        client_user_role_entity = cls.app_manager.get_entity("client_user_role")
        role_entity = cls.app_manager.get_entity("role")
        client_user_entity = cls.app_manager.get_entity("client_user")

        # Create aliases to avoid naming conflicts in joins
        role_entity_alias = aliased(role_entity)
        client_user_alias = aliased(client_user_entity)

        # Build the query with eager loading optimization
        # This prevents N+1 queries when accessing user_organization_role.organization
        stmt = (
            select(client_user_role_entity)
            .join(client_user_alias, client_user_role_entity.client_user)  # Join to access user_id
            .join(role_entity_alias, client_user_role_entity.role)  # Join to check role enabled status
            .options(
                # Eager load client_user relationship to avoid N+1
                selectinload(client_user_role_entity.client_user).selectinload(client_user_entity.client)
            )
            .where(
                client_user_alias.user_id == user_id,  # Filter by user
                role_entity_alias.enabled.is_(True)  # Only enabled roles
            )
        )

        # Optional filter: only roles that include the specified webservice
        if webservice_id is not None:
            stmt = stmt.where(role_entity_alias.webservices.any(id=webservice_id))

        # Execute query and return results with preloaded relationships
        result = await session.execute(stmt)
        organization_roles: list[ClientUserRole] = list(result.scalars().all())
        return organization_roles