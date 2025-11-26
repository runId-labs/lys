import logging
from datetime import datetime
from typing import Annotated, Optional

import strawberry
from sqlalchemy import Select, select, or_
from strawberry import relay

from lys.apps.user_auth.modules.user.consts import OBSERVATION_LOG_TYPE
from lys.apps.user_auth.modules.user.entities import User, UserAuditLog
from lys.apps.user_auth.modules.user.inputs import (
    CreateUserInput,
    CreateSuperUserInput,
    ResetPasswordInput,
    VerifyEmailInput,
    UpdateEmailInput,
    UpdatePasswordInput,
    UpdateUserPrivateDataInput,
    UpdateUserStatusInput,
    AnonymizeUserInput,
    CreateUserObservationInput,
    UpdateUserAuditLogInput
)
from lys.apps.user_auth.modules.user.nodes import (
    UserNode,
    UserStatusNode,
    GenderNode,
    PasswordResetRequestNode,
    ResetPasswordNode,
    VerifyEmailNode,
    UserOneTimeTokenNode,
    AnonymizeUserNode,
    UserAuditLogNode,
    DeleteUserObservationNode
)
from lys.apps.user_auth.modules.user.services import UserService
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.edit import lys_edition
from lys.core.graphql.fields import lys_field
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation

logger = logging.getLogger(__name__)


@register_query()
@strawberry.type
class UserQuery(Query):
    @lys_field(
        ensure_type=UserNode,
        is_public=True,
        is_licenced=False,
        description="Return the currently connected user, or null if not authenticated.",
        options={"generate_tool": True}
    )
    async def connected_user(self, info: Info) -> Optional[UserNode]:
        """
        Get the currently connected user.

        This query is public and returns the user information based on the authentication token.
        Returns None if no user is authenticated (no token or invalid token).

        Args:
            info: GraphQL context containing the connected user

        Returns:
            UserNode | None: The connected user information, or None if not authenticated
        """
        # Check if user is connected
        if not hasattr(info.context, "connected_user") or info.context.connected_user is None:
            return None

        node = UserNode.get_effective_node()
        user_service = info.context.app_manager.get_service("user")
        session = info.context.session

        # Get connected user ID from context
        connected_user_id = info.context.connected_user["id"]

        # Fetch user from database
        user = await user_service.get_by_id(connected_user_id, session)

        # Return None if user not found in database
        if user is None:
            return None

        return node.from_obj(user)

    @lys_getter(
        UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Get a specific user by ID. Returns user profile with email, status, and private data.",
        options={"generate_tool": True}
    )
    async def user(self):
        pass

    @lys_connection(
        UserNode,
        is_public=False,
        is_licenced=False,
        description="Search and list all users by name or email. Use 'search' parameter to filter. Super users only.",
        options={"generate_tool": True}
    )
    async def all_users(
        self,
        info: Info,
        search: Annotated[Optional[str], strawberry.argument(description="Search by email, first name, or last name")] = None
    ) -> Select:
        """
        Get all users in the system with optional search filtering.

        This query is only accessible to super users for administrative purposes.
        Search filters by email address, first name, or last name (case-insensitive).

        Args:
            info: GraphQL context
            search: Optional search string to filter by email, first_name, or last_name

        Returns:
            Select: SQLAlchemy select statement for users ordered by creation date
        """
        entity_type = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")

        # Base query with joins
        stmt = (
            select(entity_type)
            .join(email_entity)
            .join(private_data_entity)
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

        return stmt

    @lys_connection(
        UserNode,
        is_public=False,
        is_licenced=False,
        description="Search and list all super users by name or email. Use 'search' parameter to filter. Super users only.",
        options={"generate_tool": True}
    )
    async def all_super_users(
        self,
        info: Info,
        search: Annotated[Optional[str], strawberry.argument(description="Search by email, first name, or last name")] = None
    ) -> Select:
        """
        Get all super users in the system with optional search filtering.

        This query is only accessible to super users for administrative purposes.
        Search filters by email address, first name, or last name (case-insensitive).

        Args:
            info: GraphQL context
            search: Optional search string to filter by email, first_name, or last_name

        Returns:
            Select: SQLAlchemy select statement for super users ordered by creation date
        """
        entity_type = info.context.app_manager.get_entity("user")
        email_entity = info.context.app_manager.get_entity("user_email_address")
        private_data_entity = info.context.app_manager.get_entity("user_private_data")

        # Base query with joins, filtering only super users
        stmt = (
            select(entity_type)
            .join(email_entity)
            .join(private_data_entity)
            .where(entity_type.is_super_user == True)
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

        return stmt


@register_query()
@strawberry.type
class UserStatusQuery(Query):
    @lys_connection(
        UserStatusNode,
        is_public=True,
        is_licenced=False,
        description="List all user status types (ACTIVE, INACTIVE, SUSPENDED, DELETED). Use to get valid status codes.",
        options={"generate_tool": True}
    )
    async def all_user_statuses(
        self,
        info: Info,
        enabled: Annotated[bool | None, strawberry.argument(description="Filter by enabled status: true=active statuses, false=disabled")] = None
    ) -> Select:
        entity_type = info.context.app_manager.get_entity("user_status")
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
        return stmt


@register_query()
@strawberry.type
class GenderQuery(Query):
    @lys_connection(
        GenderNode,
        is_public=True,
        is_licenced=False,
        description="List all gender options (MALE, FEMALE, OTHER). Use to get valid gender codes for user creation.",
        options={"generate_tool": True}
    )
    async def all_genders(self, info: Info) -> Select:
        entity_type = info.context.app_manager.get_entity("gender")
        stmt = select(entity_type).order_by(entity_type.id.asc())
        return stmt


@register_query()
@strawberry.type
class UserOneTimeTokenQuery(Query):
    @lys_connection(
        ensure_type=UserOneTimeTokenNode,
        is_licenced=False,
        description="List one-time tokens (password reset, email verification) with filters by status, type, user, or date range.",
        options={"generate_tool": False}
    )
    async def all_user_one_time_tokens(
        self,
        info: Info,
        status_id: Optional[str] = None,
        type_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Select:
        entity_type = info.context.app_manager.get_entity("user_one_time_token")

        stmt = select(entity_type).order_by(entity_type.created_at.desc())

        if status_id is not None:
            stmt = stmt.where(entity_type.status_id == status_id)

        if type_id is not None:
            stmt = stmt.where(entity_type.type_id == type_id)

        if user_id is not None:
            stmt = stmt.where(entity_type.user_id == user_id)

        if start_date is not None:
            stmt = stmt.where(entity_type.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(entity_type.created_at <= end_date)

        return stmt


@register_mutation()
@strawberry.type
class UserMutation(Mutation):
    @lys_field(
        ensure_type=PasswordResetRequestNode,
        is_public=True,
        is_licenced=False,
        description="Send a password reset email to the user.",
        options={"generate_tool": False}
    )
    async def request_password_reset(self, email: str, info: Info) -> PasswordResetRequestNode:
        """
        Request a password reset email.

        Args:
            email: User's email address
            info: GraphQL context

        Returns:
            PasswordResetRequestNode with success status
        """
        node = PasswordResetRequestNode.get_effective_node()
        session = info.context.session
        user_service: type[UserService] = node.service_class

        # Delegate all business logic to the service
        await user_service.request_password_reset(
            email=email,
            session=session,
            background_tasks=info.context.background_tasks
        )

        logger.info(f"Password reset requested for email: {email}")

        return node(success=True)

    @lys_field(
        ensure_type=ResetPasswordNode,
        is_public=True,
        is_licenced=False,
        description="Reset user password using a one-time token from email.",
        options={"generate_tool": False}
    )
    async def reset_password(self, inputs: ResetPasswordInput, info: Info) -> ResetPasswordNode:
        """
        Reset user password using a one-time token.

        Args:
            inputs: Input containing:
                - token: One-time reset token from email
                - new_password: New password to set
            info: GraphQL context

        Returns:
            ResetPasswordNode with success status
        """
        input_data = inputs.to_pydantic()
        node = ResetPasswordNode.get_effective_node()
        session = info.context.session
        user_service: type[UserService] = node.service_class

        await user_service.reset_password(
            token=input_data.token,
            new_password=input_data.new_password,
            session=session
        )

        logger.info("Password successfully reset using token")

        return node(success=True)

    @lys_field(
        ensure_type=VerifyEmailNode,
        is_public=True,
        is_licenced=False,
        description="Verify user email address using a one-time token from email.",
        options={"generate_tool": False}
    )
    async def verify_email(self, inputs: VerifyEmailInput, info: Info) -> VerifyEmailNode:
        """
        Verify user email address using a one-time token.

        Args:
            inputs: Input containing:
                - token: One-time verification token from email
            info: GraphQL context

        Returns:
            VerifyEmailNode with success status
        """
        input_data = inputs.to_pydantic()
        node = VerifyEmailNode.get_effective_node()
        session = info.context.session
        user_service: type[UserService] = node.service_class

        await user_service.verify_email(
            token=input_data.token,
            session=session
        )

        logger.info("Email successfully verified using token")

        return node(success=True)

    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        is_licenced=False,
        description="Send email verification to a user. Only accessible to super users.",
        options={"generate_tool": False}
    )
    async def send_email_verification(
        self,
        obj: User,
        info: Info
    ):
        """
        Send email verification to a user and update last_validation_request_at.

        This webservice is only accessible to super users.
        It sends a verification email with a one-time token to the user's email address.
        The email must not already be validated.

        Args:
            obj: User entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            User: The user with updated last_validation_request_at timestamp

        Raises:
            LysError: If email address is already validated
        """
        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Delegate all business logic to the service
        await user_service.send_email_verification(
            user=obj,
            session=session,
            background_tasks=info.context.background_tasks
        )

        logger.info(f"Email verification sent to user {obj.id}")

        return obj

    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        is_licenced=False,
        description="Create a new super user. Only accessible to super users.",
        options={"generate_tool": True}
    )
    async def create_super_user(
        self,
        inputs: CreateSuperUserInput,
        info: Info
    ):
        """
        Create a new super user with private data.

        This webservice is only accessible to existing super users. It creates
        a new user with super user privileges and GDPR-protected private data.

        Args:
            inputs: Input containing:
                - email: Email address for the new super user
                - password: Plain text password (will be hashed)
                - language_id: Language ID for the user
                - first_name: Optional first name (GDPR-protected)
                - last_name: Optional last name (GDPR-protected)
                - gender_id: Optional gender ID (GDPR-protected)
            info: GraphQL context

        Returns:
            User: The created super user
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Delegate all business logic to the service
        user = await user_service.create_super_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code
        )

        logger.info(f"Super user created with email: {input_data.email}")

        return user

    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        is_licenced=False,
        description="Create a new regular user. Only accessible to super users.",
        options={"generate_tool": True}
    )
    async def create_user(
        self,
        inputs: CreateUserInput,
        info: Info
    ):
        """
        Create a new regular user with private data.

        This webservice is only accessible to super users. It creates
        a new user with regular privileges (not super user) and GDPR-protected private data.

        Args:
            inputs: Input containing:
                - email: Email address for the new user
                - password: Plain text password (will be hashed)
                - language_id: Language ID for the user
                - first_name: Optional first name (GDPR-protected)
                - last_name: Optional last name (GDPR-protected)
                - gender_id: Optional gender ID (GDPR-protected)
            info: GraphQL context

        Returns:
            User: The created regular user
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Delegate all business logic to the service
        user = await user_service.create_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_code,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code
        )

        logger.info(f"User created with email: {input_data.email}")

        return user

    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user email address. Only the owner can update their own email.",
        options={"generate_tool": True}
    )
    async def update_email(
        self,
        obj: User,
        inputs: UpdateEmailInput,
        info: Info
    ):
        """
        Update user email address and send verification email to the new address.

        This webservice is only accessible to the user themselves (OWNER access level).
        The new email address will be set to unverified state and a verification email
        will be sent to the new address.

        Args:
            obj: User entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - new_email: New email address
            info: GraphQL context

        Returns:
            User: The updated user with new unverified email address
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Delegate all business logic to the service
        await user_service.update_email(
            user=obj,
            new_email=input_data.new_email,
            session=session,
            background_tasks=info.context.background_tasks
        )

        logger.info(f"User {obj.id} email updated to: {input_data.new_email}")

        return obj

    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user password. Only the owner can update their own password.",
        options={"generate_tool": False}
    )
    async def update_password(
        self,
        obj: User,
        inputs: UpdatePasswordInput,
        info: Info
    ):
        """
        Update user password after verifying current password.

        This webservice is only accessible to the user themselves (OWNER access level).
        Requires current password for security.

        Args:
            obj: User entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - current_password: Current password for verification
                - new_password: New password to set
            info: GraphQL context

        Returns:
            User: The user with updated password
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        # Delegate all business logic to the service
        await user_service.update_password(
            user=obj,
            current_password=input_data.current_password,
            new_password=input_data.new_password,
            session=session
        )

        logger.info(f"User {obj.id} password updated successfully")

        return obj

    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user profile (first_name, last_name, gender, language). Owner access only.",
        options={"generate_tool": True}
    )
    async def update_user_private_data(
        self,
        obj: User,
        inputs: UpdateUserPrivateDataInput,
        info: Info
    ):
        """
        Update user private data (GDPR-protected fields) and language preference.

        This webservice is only accessible to the user themselves (OWNER access level).
        Updates first_name, last_name, gender_id, and language_id.

        Args:
            obj: User entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - first_name: Optional first name to update
                - last_name: Optional last name to update
                - gender_code: Optional gender code to update
                - language_code: Optional language code to update
            info: GraphQL context

        Returns:
            User: The user with updated private data and/or language preference
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")
        language_service = info.context.app_manager.get_service("language")

        # Delegate all business logic to the service
        await user_service.update_user(
            user=obj,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_code,
            language_id=input_data.language_code,
            session=session
        )

        logger.info(f"User {obj.id} private data updated successfully")

        return obj

    @lys_edition(
        ensure_type=UserNode,
        is_public=False,
        is_licenced=False,
        description="Update user status with audit trail. Only accessible to super users.",
        options={"generate_tool": True}
    )
    async def update_user_status(
        self,
        obj: User,
        inputs: UpdateUserStatusInput,
        info: Info
    ):
        """
        Update user status with automatic audit log creation.

        This webservice is only accessible to super users.
        Cannot be used to set status to DELETED - use anonymize_user instead.
        Creates an audit log entry with the reason and old/new status values.

        Args:
            obj: User entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - status_id: New status ID (e.g., ACTIVE, INACTIVE, SUSPENDED)
                - reason: Reason for status change (min 10 chars, for audit)
            info: GraphQL context

        Returns:
            User: The user with updated status
        """
        input_data = inputs.to_pydantic()

        session = info.context.session
        user_service = info.context.app_manager.get_service("user")

        await user_service.update_status(
            user=obj,
            status_id=input_data.status_code,
            reason=input_data.reason,
            author_user_id=info.context.connected_user["id"],
            session=session
        )

        logger.info(f"User {obj.id} status updated to: {input_data.status_code} by {info.context.connected_user['id']}")

        return obj

    @lys_field(
        ensure_type=AnonymizeUserNode,
        is_public=False,
        is_licenced=False,
        description="Anonymize user data (GDPR). Only accessible to super users. IRREVERSIBLE.",
        options={"generate_tool": True}
    )
    async def anonymize_user(self, user_id: relay.GlobalID, inputs: AnonymizeUserInput, info: Info) -> AnonymizeUserNode:
        """
        Anonymize user data for GDPR compliance.

        This is an IRREVERSIBLE operation that:
        - Sets user status to DELETED
        - Removes all private data (first_name, last_name, gender)
        - Sets anonymized_at timestamp
        - Keeps user_id and email for audit/legal purposes

        This webservice is only accessible to super users.

        Args:
            user_id: Relay GlobalID of user to anonymize
            inputs: Input containing:
                - reason: Reason for anonymization (required for audit)
            info: GraphQL context

        Returns:
            AnonymizeUserNode with success status
        """
        input_data = inputs.to_pydantic()
        node = AnonymizeUserNode.get_effective_node()
        session = info.context.session
        user_service: type[UserService] = node.service_class

        await user_service.anonymize_user(
            user_id=user_id.node_id,
            reason=input_data.reason,
            anonymized_by=info.context.connected_user["id"],
            session=session
        )

        logger.info(f"User {user_id.node_id} anonymized by {info.context.connected_user['id']}")

        return node(success=True)


@register_query()
@strawberry.type
class UserAuditLogQuery(Query):
    """
    GraphQL queries for user audit logs.

    Provides access to audit trail for user-related actions and observations.
    """

    @lys_connection(
        ensure_type=UserAuditLogNode,
        is_public=False,
        is_licenced=False,
        description="Search audit logs by type (STATUS_CHANGE, ANONYMIZATION, OBSERVATION), email, or user. Filter by author or target user.",
        options={"generate_tool": True}
    )
    async def list_user_audit_logs(
        self,
        info: Info,
        log_type_code: Annotated[Optional[str], strawberry.argument(description="Filter by log type: STATUS_CHANGE, ANONYMIZATION, or OBSERVATION")] = None,
        email_search: Annotated[Optional[str], strawberry.argument(description="Search in target or author email addresses")] = None,
        user_filter: Annotated[Optional[str], strawberry.argument(description="Filter by user role: 'author', 'target', or null for both")] = None,
        include_deleted: Annotated[Optional[bool], strawberry.argument(description="Include soft-deleted observations")] = False
    ) -> Select:
        """
        List user audit logs with optional filters.

        This query is only accessible to super users and users with USER_ADMIN role.
        Provides comprehensive filtering by log type, email search, and user role.

        Args:
            info: GraphQL context
            log_type_code: Filter by log type (STATUS_CHANGE, ANONYMIZATION, OBSERVATION)
            email_search: Search in target or author email addresses
            user_filter: Filter by user role ("author", "target", or None for both)
            include_deleted: Include soft-deleted observations (default: False)

        Returns:
            Select: SQLAlchemy select statement for audit logs
        """
        audit_log_service = info.context.app_manager.get_service("user_audit_log")

        stmt = audit_log_service.list_audit_logs(
            log_type_id=log_type_code,
            email_search=email_search,
            user_filter=user_filter,
            include_deleted=include_deleted
        )

        return stmt


@register_mutation()
@strawberry.type
class UserAuditLogMutation(Mutation):
    """
    GraphQL mutations for user audit logs.

    Provides operations for creating, updating, and deleting user observations.
    """

    @lys_creation(
        ensure_type=UserAuditLogNode,
        is_public=False,
        is_licenced=False,
        description="Create user observation (manual audit log). Only accessible to super users and USER_ADMIN role.",
        options={"generate_tool": True}
    )
    async def create_user_observation(
        self,
        inputs: CreateUserObservationInput,
        info: Info
    ):
        """
        Create a manual observation/note about a user.

        This webservice is only accessible to super users and users with USER_ADMIN role.
        Creates an OBSERVATION type audit log entry.

        Args:
            inputs: Input containing:
                - target_user_id: ID of user to create observation for
                - message: Observation message (min 10 characters)
            info: GraphQL context

        Returns:
            UserAuditLog: The created audit log
        """
        input_data = inputs.to_pydantic()
        session = info.context.session
        audit_log_service = info.context.app_manager.get_service("user_audit_log")

        audit_log = await audit_log_service.create_audit_log(
            target_user_id=input_data.target_user_id,
            author_user_id=info.context.connected_user["id"],
            log_type_id=OBSERVATION_LOG_TYPE,
            message=input_data.message,
            session=session
        )

        logger.info(
            f"Observation created for user {input_data.target_user_id} "
            f"by {info.context.connected_user['id']}"
        )

        return audit_log

    @lys_edition(
        ensure_type=UserAuditLogNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Update user audit log (OBSERVATION only). Only owner and super users can update.",
        options={"generate_tool": True}
    )
    async def update_user_audit_log(
        self,
        obj: UserAuditLog,
        inputs: UpdateUserAuditLogInput,
        info: Info
    ):
        """
        Update a user audit log message.

        This webservice is only accessible to:
        - The author of the observation (OWNER access level)
        - Super users

        Only OBSERVATION type logs can be updated.
        STATUS_CHANGE and ANONYMIZATION logs are immutable for audit integrity.

        Args:
            obj: UserAuditLog entity (fetched and validated by lys_edition)
            inputs: Input containing:
                - message: Updated observation message (min 10 characters)
            info: GraphQL context

        Returns:
            Updated obj (via lys_edition mechanism)
        """
        input_data = inputs.to_pydantic()
        session = info.context.session
        audit_log_service = info.context.app_manager.get_service("user_audit_log")

        await audit_log_service.update_observation(
            log=obj,
            new_message=input_data.message,
            session=session
        )

        logger.info(
            f"Audit log {obj.id} updated by {info.context.connected_user['id']}"
        )

    @lys_edition(
        ensure_type=DeleteUserObservationNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Delete user observation (soft delete). Only owner and super users can delete.",
        options={"generate_tool": True}
    )
    async def delete_user_observation(
        self,
        obj: UserAuditLog,
        info: Info
    ):
        """
        Soft delete a user observation.

        This webservice is only accessible to:
        - The author of the observation (OWNER access level)
        - Super users

        Only OBSERVATION type logs can be deleted.
        STATUS_CHANGE and ANONYMIZATION logs are immutable for audit integrity.

        Args:
            obj: UserAuditLog entity (fetched and validated by lys_edition)
            info: GraphQL context

        Returns:
            Deleted obj (via lys_edition mechanism, will be transformed to success=True by DeleteUserObservationNode)
        """
        session = info.context.session
        audit_log_service = info.context.app_manager.get_service("user_audit_log")

        await audit_log_service.delete_observation(
            log=obj,
            session=session
        )

        logger.info(
            f"Observation {obj.id} deleted by {info.context.connected_user['id']}"
        )
