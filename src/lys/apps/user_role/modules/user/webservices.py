import logging
from typing import Optional

import strawberry
from sqlalchemy import Select, select, or_

from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.user_role.errors import UNAUTHORIZED_ROLE_ASSIGNMENT
from lys.apps.user_role.modules.user.entities import User
from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput, UpdateUserRolesInput
from lys.apps.user_role.modules.user.services import UserService
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.errors import LysError
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.registers import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query
from lys.core.registers import override_webservice

logger = logging.getLogger(__name__)


# Override user query from user_auth to extend access levels to include ROLE
override_webservice(
    name="user",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)


@strawberry.type
@register_query()
class UserRoleQuery(Query):
    @lys_connection(
        UserNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,
        description="Return all users with optional search and role filtering. Accessible to USER_ADMIN role."
    )
    async def all_users(
        self,
        info: Info,
        search: Optional[str] = None,
        role_code: Optional[str] = None
    ) -> Select:
        """
        Get all users in the system with optional search and role filtering.

        This query is accessible to users with ROLE_ACCESS_LEVEL (e.g., USER_ADMIN_ROLE).
        Search filters by email address, first name, or last name (case-insensitive).
        Role filtering checks if users have a specific role assigned.

        Args:
            info: GraphQL context
            search: Optional search string to filter by email, first_name, or last_name
            role_code: Optional role code to filter users by.
                       Returns users who have this specific role.

        Returns:
            Select: SQLAlchemy select statement for users ordered by creation date
        """
        entity_type = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")

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

        # Apply role filter if provided
        if role_code:
            role_entity = info.context.app_manager.get_entity("role")
            # Join with roles to filter by role_code
            stmt = stmt.join(entity_type.roles).where(role_entity.id == role_code)

        return stmt


@register_mutation()
@strawberry.type
class UserMutation(Mutation):
    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,
        description="Create a new user with role assignments. Accessible to users with ROLE access level."
    )
    async def create_user(
        self,
        inputs: CreateUserWithRolesInput,
        info: Info
    ):
        """
        Create a new user with role assignments.

        This webservice is accessible to users with ROLE_ACCESS_LEVEL (e.g., USER_ADMIN_ROLE).
        Regular users can only assign roles they themselves possess. Super users can assign any role.

        Args:
            inputs: Input containing:
                - email: Email address for the new user
                - password: Plain text password (will be hashed)
                - language_id: Language ID for the user
                - first_name: Optional first name (GDPR-protected)
                - last_name: Optional last name (GDPR-protected)
                - gender_id: Optional gender ID (GDPR-protected)
                - roles: List of role IDs to assign to the new user
            info: GraphQL context

        Returns:
            User: The created user with assigned roles

        Raises:
            LysError: If user tries to assign roles they don't have (unless super user)
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        connected_user = info.context.connected_user

        # Get services via app_manager
        user_service: type[UserService] = info.context.app_manager.get_service("user")

        # Check if connected user is super user
        is_super_user = connected_user.get("is_super_user", False)

        # Validate role assignments
        if input_data.role_codes and not is_super_user:
            # Get the connected user entity to access their roles
            connected_user_entity = await user_service.get_by_id(connected_user["id"], session)

            # Get role codes that the connected user has
            connected_user_role_codes = {role.id for role in connected_user_entity.roles}

            # Check if user is trying to assign roles they don't have
            requested_role_codes = set(input_data.role_codes)
            unauthorized_roles = requested_role_codes - connected_user_role_codes

            if unauthorized_roles:
                raise LysError(
                    UNAUTHORIZED_ROLE_ASSIGNMENT,
                    f"You cannot assign roles you don't have: {', '.join(unauthorized_roles)}"
                )

        # Create the user with roles
        user = await user_service.create_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            roles=input_data.role_codes,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code
        )

        if input_data.role_codes:
            logger.info(f"User created with email: {input_data.email} and roles: {input_data.role_codes}")
        else:
            logger.info(f"User created with email: {input_data.email} without roles")

        return user

    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user role assignments. Accessible to users with USER_ADMIN role."
    )
    async def update_user_roles(
        self,
        obj: User,
        inputs: UpdateUserRolesInput,
        info: Info
    ):
        """
        Update a user's role assignments by synchronizing with the provided list.

        This webservice is accessible to users with ROLE_ACCESS_LEVEL (e.g., USER_ADMIN_ROLE).
        The target user must not be a super user (super users have all permissions by default).

        The operation synchronizes roles:
        - Adds roles that are in the list but not assigned to the user
        - Removes roles that are assigned to the user but not in the list
        - Empty list removes all roles from the user

        Args:
            obj: User entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - role_codes: List of role codes to assign to the user
            info: GraphQL context

        Returns:
            User: The user with updated roles

        Raises:
            LysError: If target user is a super user
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Update user roles (validation happens in service method)
        await user_service.update_user_roles(
            user=obj,
            role_codes=input_data.role_codes,
            session=session
        )

        logger.info(f"User {obj.id} roles updated to: {input_data.role_codes} by {info.context.connected_user['id']}")


# Override webservices from user_auth to extend access levels to include ROLE
override_webservice(
    name="update_email",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="update_password",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="update_user_private_data",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="update_user_status",
    access_levels=[ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="send_email_verification",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="create_user_observation",
    access_levels=[ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="list_user_audit_logs",
    access_levels=[ROLE_ACCESS_LEVEL]
)