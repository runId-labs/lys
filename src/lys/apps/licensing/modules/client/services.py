"""
Client service extension for licensing-specific operations.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import FREE_PLAN
from lys.apps.organization.modules.client.services import ClientService as BaseClientService
from lys.core.registries import register_service

logger = logging.getLogger(__name__)


@register_service()
class ClientService(BaseClientService):
    """
    Extended Client service with licensing-specific operations.

    Extends the base ClientService to automatically assign FREE plan
    subscription when creating a new client.
    """

    @classmethod
    async def create_client_with_owner(
        cls,
        session: AsyncSession,
        client_name: str,
        email: str,
        password: str,
        language_id: str,
        send_verification_email: bool = True,
        background_tasks=None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ):
        """
        Create a new client with an owner user and FREE plan subscription.

        Extends the base method to automatically assign the FREE plan
        subscription after client creation.

        Args:
            session: Database session
            client_name: Name of the client organization
            email: Email address for the owner user
            password: Plain text password for the owner (will be hashed)
            language_id: Language ID for the owner
            send_verification_email: Whether to send email verification email (default: True)
            background_tasks: FastAPI BackgroundTasks for scheduling email (optional)
            first_name: Optional first name of the owner
            last_name: Optional last name of the owner
            gender_id: Optional gender ID of the owner

        Returns:
            Created Client entity with FREE plan subscription
        """
        # Create client with owner using base method
        client = await super().create_client_with_owner(
            session=session,
            client_name=client_name,
            email=email,
            password=password,
            language_id=language_id,
            send_verification_email=send_verification_email,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        # Assign FREE plan subscription
        await cls._assign_free_plan(client.id, session)

        return client

    @classmethod
    async def _assign_free_plan(cls, client_id: str, session: AsyncSession) -> None:
        """
        Assign the FREE plan subscription to a newly created client.

        This method is called automatically during client creation.
        It assigns the current enabled version of the FREE plan.

        Args:
            client_id: The ID of the newly created client
            session: Database session
        """
        plan_version_entity = cls.app_manager.get_entity("license_plan_version")
        subscription_entity = cls.app_manager.get_entity("subscription")

        # Get FREE plan's current (enabled) version
        stmt = select(plan_version_entity).where(
            plan_version_entity.plan_id == FREE_PLAN,
            plan_version_entity.enabled == True
        )
        result = await session.execute(stmt)
        free_version = result.scalar_one_or_none()

        if not free_version:
            logger.warning(
                "FREE plan version not found. Ensure licensing fixtures are loaded. "
                f"Client {client_id} created without subscription."
            )
            return

        # Create subscription (no Stripe for free plan)
        subscription = subscription_entity(
            client_id=client_id,
            plan_version_id=free_version.id,
            stripe_subscription_id=None
        )

        session.add(subscription)
        await session.flush()
        logger.info(f"Assigned FREE plan (version {free_version.version}) to client {client_id}")