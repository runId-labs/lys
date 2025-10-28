import strawberry
from sqlalchemy import Select, select

from lys.apps.user_auth.modules.user.nodes import UserNode, UserStatusNode, ForgottenPasswordNode

from lys.apps.user_auth.modules.user.services import UserStatusService, UserService, UserEmailingService
from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.fields import lys_field
from lys.core.graphql.getter import lys_getter
from lys.core.graphql.registers import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation


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
        entity_type = service_class.get_entity_by_name("user_status")
        stmt = select(entity_type).order_by(entity_type.id.asc())
        if enabled is not None:
            stmt = stmt.where(entity_type.enabled == enabled)
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
        from lys.apps.base.tasks import send_pending_email

        node = ForgottenPasswordNode.get_effective_node()
        session = info.context.session

        # Get services
        user_service: type[UserService] = node.service_class
        user_emailing_service: type[UserEmailingService] = user_service.get_service_by_name("user_emailing")

        # Find user by email
        user = await user_service.get_by_email(email, session)

        # Don't reveal if email exists or not (security)
        if not user:
            return node(success=True)

        # Create emailing (will be committed at end of request)
        user_emailing = await user_emailing_service.create_forgotten_password_emailing(
            user, session
        )

        # Send email via Celery after commit
        # Note: This will be executed after the session commits
        info.context.background_tasks.add_task(
            lambda: send_pending_email.delay(user_emailing.emailing_id)
        )

        return node(success=True)