import logging
from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select, or_, exists
from strawberry import relay

from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.organization.modules.user.entities import ClientUser
from lys.apps.organization.modules.user.inputs import (
    CreateClientUserInput,
    UpdateClientUserEmailInput,
    UpdateClientUserPrivateDataInput,
    UpdateClientUserRolesInput
)
from lys.apps.organization.modules.user.nodes import ClientUserNode
from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation

logger = logging.getLogger(__name__)


@strawberry.type
@register_query()
class OrganizationUserQuery(Query):
    @lys_connection(
        UserNode,
        access_levels=[ROLE_ACCESS_LEVEL],
        is_licenced=False,
        allow_override=True,
        description="Search and list all regular users (excludes super users). Use 'search' to filter by name or email, 'is_client_user' to filter by organization membership (true=in org, false=not in org), 'role_code' to filter by role.",
        options={"generate_tool": True}
    )
    async def all_users(
        self,
        info: Info,
        search: Annotated[Optional[str], strawberry.argument(description="Search term to filter by email, first name, or last name")] = None,
        is_client_user: Annotated[Optional[bool], strawberry.argument(description="Filter by organization membership: true=with org, false=without org")] = None,
        role_code: Annotated[Optional[str], strawberry.argument(description="Filter by role code (e.g., 'ADMIN', 'USER_ADMIN')")] = None
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
                - False: users with no client_user relationships AND not a client owner
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
                # Also exclude users who are client owners
                client_entity = info.context.app_manager.get_entity("client")
                client_owner_exists = exists().where(
                    client_entity.owner_id == entity_type.id
                )
                stmt = stmt.where(~client_user_exists & ~client_owner_exists)

        # Apply role filter if provided
        if role_code:
            role_entity = info.context.app_manager.get_entity("role")
            # Join with roles to filter by role_code
            stmt = stmt.join(entity_type.roles).where(role_entity.id == role_code)

        return stmt

    @lys_getter(
        ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Get user details within an organization by client_user ID. Returns user profile, email, and organization roles.",
        options={"generate_tool": True}
    )
    async def client_user(self, obj: ClientUser, info: Info):
        pass

    @lys_connection(
        ClientUserNode,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Search users within organizations. Use 'client_id' to filter by organization, 'search' for name/email, 'role_code' for organization role.",
        options={"generate_tool": True}
    )
    async def all_client_users(
        self,
        info: Info,
        client_id: Annotated[Optional[relay.GlobalID], strawberry.argument(description="Filter by organization/client ID")] = None,
        search: Annotated[Optional[str], strawberry.argument(description="Search by user email, first name, or last name")] = None,
        role_code: Annotated[Optional[str], strawberry.argument(description="Filter by organization role code")] = None
    ) -> Select:
        """
        Get all client-user relationships with optional filtering.

        This query is accessible to users with ROLE or ORGANIZATION_ROLE access level.
        Returns the many-to-many relationships between clients and users.

        Args:
            info: GraphQL context
            client_id: Optional GlobalID to filter by specific client
            search: Optional search string to filter by user's email, first_name, or last_name
            role_code: Optional role code to filter client users by organization role

        Returns:
            Select: SQLAlchemy select statement for client_user relationships ordered by creation date
        """
        client_user_entity = info.context.app_manager.get_entity("client_user")
        user_entity = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")

        # Base query with joins for search functionality
        stmt = select(client_user_entity)

        # Join with user, email, and private_data if search is provided
        if search:
            stmt = (
                stmt
                .join(user_entity, client_user_entity.user)
                .join(email_entity)
                .join(private_data_entity)
            )

            search_pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    email_entity.id.ilike(search_pattern),
                    private_data_entity.first_name.ilike(search_pattern),
                    private_data_entity.last_name.ilike(search_pattern)
                )
            )

        # Apply client filter if provided
        if client_id:
            stmt = stmt.where(client_user_entity.client_id == client_id.node_id)

        # Apply role filter if provided
        if role_code:
            client_user_role_entity = info.context.app_manager.get_entity("client_user_role")
            role_entity = info.context.app_manager.get_entity("role")

            # Join with client_user_roles to filter by role_code
            stmt = (
                stmt
                .join(client_user_role_entity, client_user_entity.client_user_roles)
                .join(role_entity, client_user_role_entity.role)
                .where(role_entity.id == role_code)
            )

        stmt = stmt.order_by(client_user_entity.created_at.desc())

        return stmt


@register_mutation()
@strawberry.type
class OrganizationUserMutation(Mutation):
    @lys_edition(
        ensure_type=ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user email within organization. Required: id (client_user ID), inputs.new_email.",
        options={"generate_tool": True}
    )
    async def update_client_user_email(
        self,
        obj: ClientUser,
        inputs: UpdateClientUserEmailInput,
        info: Info
    ):
        """
        Update client user email address and send verification email to the new address.

        This webservice is accessible to users with ROLE or ORGANIZATION_ROLE access level.
        The new email address will be set to unverified state and a verification email
        will be sent to the new address.

        Args:
            obj: ClientUser entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - new_email: New email address
            info: GraphQL context

        Returns:
            ClientUser: The updated client user with new unverified email address
        """
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Update the underlying user's email
        await user_service.update_email(
            user=obj.user,
            new_email=input_data.new_email,
            session=session,
            background_tasks=info.context.background_tasks
        )

        logger.info(
            f"Client user {obj.id} email updated to: {input_data.new_email} "
            f"by {info.context.connected_user['sub']}"
        )

        return obj

    @lys_edition(
        ensure_type=ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user profile within organization. Required: id. Optional inputs: first_name, last_name, gender_code, language_code.",
        options={"generate_tool": True}
    )
    async def update_client_user_private_data(
        self,
        obj: ClientUser,
        inputs: UpdateClientUserPrivateDataInput,
        info: Info
    ):
        """
        Update client user private data (GDPR-protected fields) and language preference.

        This webservice is accessible to users with ROLE or ORGANIZATION_ROLE access level.
        Updates first_name, last_name, gender_id, and language_id of the underlying user.

        Args:
            obj: ClientUser entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - first_name: Optional first name to update
                - last_name: Optional last name to update
                - gender_code: Optional gender code to update
                - language_code: Optional language code to update
            info: GraphQL context

        Returns:
            ClientUser: The client user with updated private data
        """
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Update the underlying user's private data
        await user_service.update_user(
            user=obj.user,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code,
            language_id=input_data.language_code,
            session=session
        )

        logger.info(
            f"Client user {obj.id} private data updated by {info.context.connected_user['sub']}"
        )

        return obj

    @lys_edition(
        ensure_type=ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user's organization roles. Required: id (client_user ID), inputs.role_codes (list of role codes). Empty list removes all roles.",
        options={"generate_tool": True}
    )
    async def update_client_user_roles(
        self,
        obj: ClientUser,
        inputs: UpdateClientUserRolesInput,
        info: Info
    ):
        """
        Update a client user's role assignments within their organization by synchronizing with the provided list.

        This webservice is accessible to users with ROLE or ORGANIZATION_ROLE access level.
        The operation synchronizes organization-specific roles (ClientUserRole):
        - Adds roles that are in the list but not assigned to the client user
        - Removes roles that are assigned to the client user but not in the list
        - Empty list removes all organization roles from the client user

        Args:
            obj: ClientUser entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - role_codes: List of role codes to assign to the client user in their organization
            info: GraphQL context

        Returns:
            ClientUser: The client user with updated organization roles

        Note:
            This updates organization-specific roles (ClientUserRole), not global user roles.
        """
        input_data = inputs.to_pydantic()

        session = info.context.session
        client_user_service = info.context.app_manager.get_service("client_user")

        # Update client user's organization roles
        await client_user_service.update_client_user_roles(
            client_user=obj,
            role_codes=input_data.role_codes,
            session=session
        )

        logger.info(
            f"Client user {obj.id} roles updated to: {input_data.role_codes} "
            f"by {info.context.connected_user['sub']}"
        )

        return obj

    @lys_creation(
        ensure_type=ClientUserNode,
        is_public=False,
        access_levels=[ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL],
        is_licenced=False,
        description="Create a new user in an organization. Required: client_id, email, password, language_code. Optional: first_name, last_name, gender_code, role_codes.",
        options={"generate_tool": True}
    )
    async def create_client_user(
        self,
        inputs: CreateClientUserInput,
        info: Info
    ):
        """
        Create a new user and associate them with a client organization.

        This webservice is accessible to users with ROLE or ORGANIZATION_ROLE access level.
        It creates a new user and a ClientUser relationship linking them to the specified client.
        Organization roles can optionally be assigned during creation.

        Args:
            inputs: Input containing:
                - client_id: GlobalID of the client/organization to associate the user with
                - email: Email address for the new user
                - password: Password for the new user
                - language_code: Language code for the user
                - first_name: Optional first name (GDPR-protected)
                - last_name: Optional last name (GDPR-protected)
                - gender_code: Optional gender code (MALE, FEMALE, OTHER)
                - role_codes: Optional list of organization role codes to assign
            info: GraphQL context

        Returns:
            ClientUser: The created client user with organization roles
        """
        input_data = inputs.to_pydantic()

        session = info.context.session
        client_user_service = info.context.app_manager.get_service("client_user")

        client_user = await client_user_service.create_client_user(
            session=session,
            client_id=input_data.client_id,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code,
            role_codes=input_data.role_codes
        )

        logger.info(
            f"Client user created for client {input_data.client_id} with email {input_data.email} "
            f"by {info.context.connected_user['sub']}"
        )

        return client_user