from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity
from lys.apps.organization.modules.user.entities import User, ClientUserRole
from lys.apps.user_role.errors import SUPERVISOR_ONLY_ROLE
from lys.apps.user_role.modules.user.services import UserService as UserRoleService
from lys.core.errors import LysError
from lys.core.registries import register_service


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
        ClientUserRole → User → Client (with role/webservice filter)

        Args:
            user_id: The ID of the user to query roles for
            session: Database session for executing the query
            webservice_id: Optional webservice ID to filter roles that include this webservice

        Returns:
            List of ClientUserRole entities with preloaded organization relationships

        Note:
            Currently only supports ClientUserRole. Future implementations may need to
            support additional organization types (e.g., DepartmentUserRole, DivisionUserRole).
        """
        client_user_role_entity = cls.app_manager.get_entity("client_user_role")
        role_entity = cls.app_manager.get_entity("role")
        user_entity = cls.app_manager.get_entity("user")

        role_entity_alias = aliased(role_entity)

        # Build the query with eager loading optimization
        stmt = (
            select(client_user_role_entity)
            .join(role_entity_alias, client_user_role_entity.role)
            .options(
                # Eager load user and client relationships to avoid N+1
                selectinload(client_user_role_entity.user).selectinload(user_entity.client)
            )
            .where(
                client_user_role_entity.user_id == user_id,
                role_entity_alias.enabled.is_(True)
            )
        )

        # Optional filter: only roles that include the specified webservice
        if webservice_id is not None:
            role_webservice_entity = cls.app_manager.get_entity("role_webservice")
            stmt = stmt.where(
                exists(
                    select(role_webservice_entity.id).where(
                        role_webservice_entity.role_id == role_entity_alias.id,
                        role_webservice_entity.webservice_id == webservice_id
                    )
                )
            )

        result = await session.execute(stmt)
        organization_roles: list[ClientUserRole] = list(result.scalars().all())

        return organization_roles

    @classmethod
    async def create_client_user(
        cls,
        session: AsyncSession,
        client_id: str,
        email: str,
        password: str,
        language_id: str,
        inviter: User | None = None,
        background_tasks=None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None,
        role_codes: list[str] | None = None
    ) -> User:
        """
        Create a new user and associate them with a client organization.

        This method:
        1. Creates a new user with client_id set (no verification email)
        2. Assigns organization roles if provided
        3. Sends invitation email with activation link (if inviter provided)

        Args:
            session: Database session
            client_id: ID of the client to associate the user with
            email: Email address for the new user
            password: Plain text password (will be hashed)
            language_id: Language ID for the user
            inviter: User who is inviting this new user (for invitation email)
            background_tasks: FastAPI BackgroundTasks for scheduling email
            first_name: Optional first name (GDPR-protected)
            last_name: Optional last name (GDPR-protected)
            gender_id: Optional gender ID
            role_codes: Optional list of organization role codes to assign

        Returns:
            Created User entity with client_id set
        """
        # Create the user without verification email (invitation email will be sent instead)
        user = await cls.create_user(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            send_verification_email=False,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        # Set client_id to associate with organization
        user.client_id = client_id
        await session.flush()

        # Assign organization roles if provided
        if role_codes:
            await cls._assign_client_user_roles(user, role_codes, session)

        # Send invitation email if inviter is provided
        if inviter is not None:
            await cls.send_invitation_email(user, inviter, session, background_tasks)

        return user

    @classmethod
    async def _assign_client_user_roles(
        cls,
        user: User,
        role_codes: list[str],
        session: AsyncSession
    ) -> None:
        """
        Assign organization roles to a client user.

        Args:
            user: User entity to assign roles to (must have client_id set)
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

        # Check for supervisor_only roles - client users cannot have these
        supervisor_only_roles = [r for r in roles if r.supervisor_only]
        if supervisor_only_roles:
            role_ids = ", ".join(r.id for r in supervisor_only_roles)
            raise LysError(SUPERVISOR_ONLY_ROLE, f"Cannot assign supervisor-only roles to client user: {role_ids}")

        # Create ClientUserRole entities
        for role in roles:
            client_user_role = client_user_role_entity(
                user_id=user.id,
                role_id=role.id
            )
            session.add(client_user_role)

    @classmethod
    async def update_client_user_roles(
        cls,
        user: User,
        role_codes: list[str],
        session: AsyncSession
    ) -> None:
        """
        Update a client user's role assignments within their organization by synchronizing with the provided list.

        This method:
        - Adds roles that are in the list but not assigned to the user
        - Removes roles that are assigned to the user but not in the list
        - Empty list removes all roles from the user

        Args:
            user: User entity to update roles for (must have client_id set)
            role_codes: List of role codes to assign to the user in their organization
            session: Database session for executing queries

        Note:
            This updates organization-specific roles (ClientUserRole), not global user roles.
        """
        # Get current role codes from client_user_roles
        current_role_codes = {cur.role.id for cur in user.client_user_roles}

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

            # Check for supervisor_only roles - client users cannot have these
            supervisor_only_roles = [r for r in roles_to_add_entities if r.supervisor_only]
            if supervisor_only_roles:
                role_ids = ", ".join(r.id for r in supervisor_only_roles)
                raise LysError(SUPERVISOR_ONLY_ROLE, f"Cannot assign supervisor-only roles to client user: {role_ids}")

            # Create ClientUserRole entities for new roles
            client_user_role_entity = cls.app_manager.get_entity("client_user_role")
            for role in roles_to_add_entities:
                client_user_role = client_user_role_entity(
                    user_id=user.id,
                    role_id=role.id
                )
                session.add(client_user_role)

        # Remove roles that are no longer in the list
        if roles_to_remove:
            for client_user_role in list(user.client_user_roles):
                if client_user_role.role.id in roles_to_remove:
                    await session.delete(client_user_role)