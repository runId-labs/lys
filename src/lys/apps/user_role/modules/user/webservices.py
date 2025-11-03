import logging

import strawberry

from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.apps.user_role.errors import UNAUTHORIZED_ROLE_ASSIGNMENT
from lys.apps.user_role.modules.user.inputs import CreateUserWithRolesInput
from lys.apps.user_role.modules.user.services import UserService
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.errors import LysError
from lys.core.graphql.create import lys_creation
from lys.core.graphql.registers import register_mutation
from lys.core.graphql.types import Mutation
from lys.core.registers import override_webservice

logger = logging.getLogger(__name__)


# Override user query from user_auth to extend access levels to include ROLE
override_webservice(
    name="user",
    access_levels=[OWNER_ACCESS_LEVEL, ROLE_ACCESS_LEVEL]
)


@register_mutation("graphql")
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
    name="create_user_observation",
    access_levels=[ROLE_ACCESS_LEVEL]
)

override_webservice(
    name="list_user_audit_logs",
    access_levels=[ROLE_ACCESS_LEVEL]
)