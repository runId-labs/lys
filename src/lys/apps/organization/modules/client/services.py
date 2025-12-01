import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.client.entities import Client
from lys.core.registries import register_service
from lys.core.services import EntityService

logger = logging.getLogger(__name__)


@register_service()
class ClientService(EntityService[Client]):
    """
    Service for managing Client entities.

    Provides business logic for client creation, updates, and queries.
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
    ) -> Client:
        """
        Create a new client with an owner user.

        This method performs the following operations in a transaction:
        1. Creates a new user who will be the client owner
        2. Creates the client with the user as owner
        3. Creates a ClientUser relationship linking the owner to the client

        The owner will have automatic full administrative access to the client
        without requiring explicit role assignments (via client.owner_id check).

        The owner user can be accessed via client.owner relationship.

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
            Created Client entity (access owner via client.owner)

        Raises:
            LysError: If email already exists, language doesn't exist, or gender doesn't exist
        """
        # Get required services
        user_service = cls.app_manager.get_service("user")
        client_user_entity = cls.app_manager.get_entity("client_user")

        # Step 1: Create the owner user
        owner_user = await user_service.create_user(
            session=session,
            email=email,
            password=password,
            language_id=language_id,
            send_verification_email=send_verification_email,
            background_tasks=background_tasks,
            first_name=first_name,
            last_name=last_name,
            gender_id=gender_id
        )

        # Step 2: Create the client with the user as owner
        client = cls.entity_class(
            name=client_name,
            owner_id=owner_user.id
        )

        session.add(client)
        await session.flush()
        await session.refresh(client)

        # Step 3: Create ClientUser relationship to link owner to client
        client_user = client_user_entity(
            user_id=owner_user.id,
            client_id=client.id
        )

        session.add(client_user)
        await session.flush()

        # Step 4: Assign FREE plan subscription (if licensing app is enabled)
        await cls._assign_free_plan(client.id, session)

        return client

    @classmethod
    async def _assign_free_plan(cls, client_id: str, session: AsyncSession) -> None:
        """
        Assign the FREE plan subscription to a newly created client.

        This method is called automatically during client creation.
        It assigns the current enabled version of the FREE plan.

        If the licensing app is not enabled or the FREE plan doesn't exist,
        this method logs a warning and skips subscription creation.

        Args:
            client_id: The ID of the newly created client
            session: Database session
        """
        # Check if licensing entities are available
        try:
            plan_version_entity = cls.app_manager.get_entity("license_plan_version")
            subscription_entity = cls.app_manager.get_entity("subscription")
        except KeyError:
            # Licensing app not enabled - skip
            logger.debug("Licensing app not enabled, skipping FREE plan assignment")
            return

        # Import here to avoid circular imports when licensing app is not enabled
        from lys.apps.licensing.consts import FREE_PLAN

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