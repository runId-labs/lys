"""
Client user services for licensing app.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import MAX_USERS
from lys.apps.licensing.errors import NO_ACTIVE_SUBSCRIPTION, MAX_LICENSED_USERS_REACHED
from lys.apps.organization.modules.user.entities import ClientUser
from lys.apps.organization.modules.user.services import ClientUserService as BaseClientUserService
from lys.core.errors import LysError
from lys.core.registries import register_service


@register_service()
class ClientUserService(BaseClientUserService):
    """
    Extended ClientUserService with licensing operations.
    """

    @classmethod
    async def add_to_subscription(
        cls,
        client_user: ClientUser,
        session: AsyncSession
    ) -> None:
        """
        Add a client user to their client's subscription.

        Finds the subscription for the client user's client and adds them to it.
        Validates MAX_USERS quota before adding.

        Args:
            client_user: ClientUser entity
            session: Database session

        Raises:
            LysError: If client has no subscription, user is already licensed,
                      or MAX_USERS quota is exceeded
        """
        subscription_service = cls.app_manager.get_service("subscription")
        license_checker_service = cls.app_manager.get_service("license_checker")

        # Get the client's subscription
        subscription = await subscription_service.get_client_subscription(
            client_user.client_id, session
        )
        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_user.client_id} has no active subscription"
            )

        # Check MAX_USERS quota before adding
        await license_checker_service.enforce_quota(
            client_user.client_id, MAX_USERS, session,
            error=MAX_LICENSED_USERS_REACHED
        )

        # Add user to subscription
        await subscription_service.add_user_to_subscription(
            subscription.id, client_user.id, session
        )

    @classmethod
    async def remove_from_subscription(
        cls,
        client_user: ClientUser,
        session: AsyncSession
    ) -> None:
        """
        Remove a client user from their client's subscription.

        Finds the subscription for the client user's client and removes them from it.

        Args:
            client_user: ClientUser entity
            session: Database session

        Raises:
            LysError: If client has no subscription or user is not licensed
        """
        subscription_service = cls.app_manager.get_service("subscription")

        # Get the client's subscription
        subscription = await subscription_service.get_client_subscription(
            client_user.client_id, session
        )
        if not subscription:
            raise LysError(
                NO_ACTIVE_SUBSCRIPTION,
                f"Client {client_user.client_id} has no active subscription"
            )

        # Remove user from subscription
        await subscription_service.remove_user_from_subscription(
            subscription.id, client_user.id, session
        )