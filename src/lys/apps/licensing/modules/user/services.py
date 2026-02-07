"""
User services for licensing app.
"""

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import MAX_USERS
from lys.apps.licensing.errors import NO_ACTIVE_SUBSCRIPTION, MAX_LICENSED_USERS_REACHED
from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED, LICENSE_REVOKED
from lys.apps.organization.modules.user.entities import User
from lys.apps.organization.modules.user.services import UserService as BaseUserService
from lys.apps.user_auth.modules.event.tasks import trigger_event
from lys.core.errors import LysError
from lys.core.registries import register_service


@register_service()
class UserService(BaseUserService):
    """
    Extended UserService with licensing operations.
    """

    @classmethod
    async def add_to_subscription(
        cls,
        user: User,
        session: AsyncSession,
        background_tasks: BackgroundTasks
    ) -> None:
        """
        Add a user to their client's subscription.

        Finds the subscription for the user's client and adds them to it.
        Validates MAX_USERS quota before adding.

        Args:
            user: User entity (must have client_id set)
            session: Database session
            background_tasks: FastAPI background tasks for event triggering

        Raises:
            LysError: If client has no subscription, user is already licensed,
                      or MAX_USERS quota is exceeded
        """
        subscription_service = cls.app_manager.get_service("subscription")
        license_checker_service = cls.app_manager.get_service("license_checker")

        # Get the client's subscription
        subscription = await subscription_service.get_client_subscription(
            user.client_id, session
        )
        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {user.client_id} has no active subscription"
            )

        # Check MAX_USERS quota before adding
        await license_checker_service.enforce_quota(
            user.client_id, MAX_USERS, session,
            error=MAX_LICENSED_USERS_REACHED
        )

        # Add user to subscription
        await subscription_service.add_user_to_subscription(
            subscription.id, user.id, session
        )

        # Trigger LICENSE_GRANTED event after commit
        user_id = str(user.id)
        license_name = subscription.plan_version.plan.name if subscription.plan_version else "License"
        client_name = user.client.name if user.client else None
        client_id = user.client_id

        background_tasks.add_task(
            lambda: trigger_event.delay(
                event_type=LICENSE_GRANTED,
                user_id=user_id,
                notification_data={
                    "license_name": license_name,
                    "client_name": client_name,
                },
                organization_data={"client_ids": [client_id]} if client_id else None,
            )
        )

    @classmethod
    async def remove_from_subscription(
        cls,
        user: User,
        session: AsyncSession,
        background_tasks: BackgroundTasks
    ) -> None:
        """
        Remove a user from their client's subscription.

        Finds the subscription for the user's client and removes them from it.

        Args:
            user: User entity (must have client_id set)
            session: Database session
            background_tasks: FastAPI background tasks for event triggering

        Raises:
            LysError: If client has no subscription or user is not licensed
        """
        subscription_service = cls.app_manager.get_service("subscription")

        # Get the client's subscription
        subscription = await subscription_service.get_client_subscription(
            user.client_id, session
        )
        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {user.client_id} has no active subscription"
            )

        # Remove user from subscription
        await subscription_service.remove_user_from_subscription(
            subscription.id, user.id, session
        )

        # Trigger LICENSE_REVOKED event after commit
        user_id = str(user.id)
        license_name = subscription.plan_version.plan.name if subscription.plan_version else "License"
        client_name = user.client.name if user.client else None
        client_id = user.client_id

        background_tasks.add_task(
            lambda: trigger_event.delay(
                event_type=LICENSE_REVOKED,
                user_id=user_id,
                notification_data={
                    "license_name": license_name,
                    "client_name": client_name,
                },
                organization_data={"client_ids": [client_id]} if client_id else None,
            )
        )