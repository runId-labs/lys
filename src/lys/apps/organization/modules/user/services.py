from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity
from lys.apps.organization.modules.user.entities import ClientUser, ClientUserRole
from lys.apps.user_role.modules.user.services import UserService as UserRoleService
from lys.core.registries import register_service
from lys.core.services import EntityService


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


@register_service()
class ClientUserService(EntityService[ClientUser]):
    """
    Service for managing ClientUser entity (many-to-many relationship between Client and User).
    """

    @classmethod
    async def create_client_user(
        cls,
        session: AsyncSession,
        client_id: str,
        email: str,
        password: str,
        language_id: str,
        send_verification_email: bool = True,
        background_tasks=None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None,
        role_codes: list[str] | None = None
    ) -> ClientUser:
        """
        Create a new user and associate them with a client organization.

        This method:
        1. Creates a new user via user_service.create_user()
        2. Creates a ClientUser relationship linking the user to the client
        3. Assigns organization roles if provided

        Args:
            session: Database session
            client_id: ID of the client to associate the user with
            email: Email address for the new user
            password: Plain text password (will be hashed)
            language_id: Language ID for the user
            send_verification_email: Whether to send email verification (default: True)
            background_tasks: FastAPI BackgroundTasks for scheduling email
            first_name: Optional first name (GDPR-protected)
            last_name: Optional last name (GDPR-protected)
            gender_id: Optional gender ID
            role_codes: Optional list of organization role codes to assign

        Returns:
            Created ClientUser entity
        """
        user_service = cls.app_manager.get_service("user")

        # Step 1: Create the user
        user = await user_service.create_user(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            send_verification_email=send_verification_email,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        # Step 2: Create ClientUser relationship
        client_user = cls.entity_class(
            user_id=user.id,
            client_id=client_id
        )
        session.add(client_user)
        await session.flush()

        # Step 3: Assign organization roles if provided
        if role_codes:
            await cls._assign_roles(client_user, role_codes, session)

        return client_user

    @classmethod
    async def _assign_roles(
        cls,
        client_user: ClientUser,
        role_codes: list[str],
        session: AsyncSession
    ) -> None:
        """
        Assign organization roles to a client user.

        Args:
            client_user: ClientUser entity to assign roles to
            role_codes: List of role codes to assign
            session: Database session
        """
        role_service = cls.app_manager.get_service("role")
        role_entity = role_service.entity_class
        client_user_role_entity = cls.app_manager.get_entity("client_user_role")

        # Fetch role entities
        stmt = select(role_entity).where(role_entity.id.in_(role_codes))
        result = await session.execute(stmt)
        roles = list(result.scalars().all())

        # Create ClientUserRole entities
        for role in roles:
            client_user_role = client_user_role_entity(
                client_user_id=client_user.id,
                role_id=role.id
            )
            session.add(client_user_role)

    @classmethod
    async def update_client_user_roles(
        cls,
        client_user: ClientUser,
        role_codes: list[str],
        session: AsyncSession
    ) -> None:
        """
        Update a client user's role assignments within their organization by synchronizing with the provided list.

        This method:
        - Adds roles that are in the list but not assigned to the client user
        - Removes roles that are assigned to the client user but not in the list
        - Empty list removes all roles from the client user

        Args:
            client_user: ClientUser entity to update roles for
            role_codes: List of role codes to assign to the client user in their organization
            session: Database session for executing queries

        Note:
            This updates organization-specific roles (ClientUserRole), not global user roles.
        """
        # Get current role codes from client_user_roles
        current_role_codes = {cur.role.id for cur in client_user.client_user_roles}

        # Get target role codes
        target_role_codes = set(role_codes)

        # Determine which roles to add and remove
        roles_to_add = target_role_codes - current_role_codes
        roles_to_remove = current_role_codes - target_role_codes

        # Fetch role entities to add
        if roles_to_add:
            role_service = cls.app_manager.get_service("role")
            role_entity = role_service.entity_class

            stmt = select(role_entity).where(role_entity.id.in_(roles_to_add))
            result = await session.execute(stmt)
            roles_to_add_entities = list(result.scalars().all())

            # Create ClientUserRole entities for new roles
            client_user_role_entity = cls.app_manager.get_entity("client_user_role")
            for role in roles_to_add_entities:
                client_user_role = client_user_role_entity(
                    client_user_id=client_user.id,
                    role_id=role.id
                )
                session.add(client_user_role)

        # Remove roles that are no longer in the list
        if roles_to_remove:
            # Delete ClientUserRole entries
            for client_user_role in list(client_user.client_user_roles):
                if client_user_role.role.id in roles_to_remove:
                    await session.delete(client_user_role)