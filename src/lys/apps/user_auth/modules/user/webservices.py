import logging
from datetime import datetime
from typing import Optional

import strawberry
from sqlalchemy import Select, select

from lys.apps.user_auth.modules.user.inputs import (
    CreateUserInput,
    CreateSuperUserInput,
    ResetPasswordInput
)
from lys.apps.user_auth.modules.user.nodes import (
    UserNode,
    UserStatusNode,
    ForgottenPasswordNode,
    ResetPasswordNode,
    UserOneTimeTokenNode
)
from lys.apps.user_auth.modules.user.services import UserStatusService, UserService
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.create import lys_creation
from lys.core.graphql.fields import lys_field
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registers import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation

logger = logging.getLogger(__name__)


@register_query("graphql")
@strawberry.type
class UserQuery(Query):
    @lys_getter(
        UserNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Return user information."
    )
    async def user(self):
        pass


@register_query("graphql")
@strawberry.type
class UserStatusQuery(Query):
    @lys_connection(
        UserStatusNode,
        is_public=True,
        is_licenced=False,
        description="Return all possible user statuses."
    )
    async def all_user_statuses(self, info: Info, enabled: bool | None = None) -> Select:
        service_class: type[UserStatusService] | None = info.context.service_class
        entity_type = service_class.app_manager.get_entity("user_status")
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
        return stmt


@register_query("graphql")
@strawberry.type
class UserOneTimeTokenQuery(Query):
    @lys_connection(
        ensure_type=UserOneTimeTokenNode,
        is_licenced=False,
        description="Return user one-time tokens filtered by optional criteria."
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
        entity_type = info.context.service_class.entity_class

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


@register_mutation("graphql")
@strawberry.type
class UserMutation(Mutation):
    @lys_field(
        ensure_type=ForgottenPasswordNode,
        is_public=True,
        is_licenced=False,
        description="Send a password reset email to the user."
    )
    async def forgotten_password(self, email: str, info: Info) -> ForgottenPasswordNode:
        """
        Request a password reset email.

        Args:
            email: User's email address
            info: GraphQL context

        Returns:
            ForgottenPasswordNode with success status
        """
        node = ForgottenPasswordNode.get_effective_node()
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
        description="Reset user password using a one-time token from email."
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

    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        is_licenced=False,
        description="Create a new super user. Only accessible to super users."
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
        user_service: type[UserService] = info.context.service_class

        # Delegate all business logic to the service
        user = await user_service.create_super_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_id,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_id
        )

        logger.info(f"Super user created with email: {input_data.email}")

        return user

    @lys_creation(
        ensure_type=UserNode,
        is_public=False,
        is_licenced=False,
        description="Create a new regular user. Only accessible to super users."
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
        user_service: type[UserService] = info.context.service_class

        # Delegate all business logic to the service
        user = await user_service.create_user(
            session=session,
            email=input_data.email,
            password=input_data.password,
            language_id=input_data.language_id,
            send_verification_email=True,
            background_tasks=info.context.background_tasks,
            first_name=input_data.first_name,
            last_name=input_data.last_name,
            gender_id=input_data.gender_id
        )

        logger.info(f"User created with email: {input_data.email}")

        return user
