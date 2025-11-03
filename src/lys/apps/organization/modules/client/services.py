from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.client.entities import Client
from lys.core.registers import register_service
from lys.core.services import EntityService


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

        return client