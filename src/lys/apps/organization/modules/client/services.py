from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.client.entities import Client
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc


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
        3. Associates the owner user with the client via user.client_id

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
        user_service = cls.app_manager.get_service("user")

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

        # Step 3: Associate the owner user with the client
        owner_user.client_id = client.id
        await session.flush()

        return client

    @classmethod
    async def create_client_with_sso_owner(
        cls,
        session: AsyncSession,
        client_name: str,
        sso_token: str,
        language_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        gender_id: str | None = None
    ) -> Client:
        """
        Create a new client with an SSO-authenticated owner (no password).

        This method:
        1. Consumes SSO session from Redis
        2. Creates user with no password (SSO-only), email marked as validated
        3. Creates the client with the user as owner
        4. Creates the UserSSOLink
        """
        sso_auth_service = cls.app_manager.get_service("sso_auth")
        user_service = cls.app_manager.get_service("user")
        sso_link_service = cls.app_manager.get_service("user_sso_link")

        # 1. Consume SSO session (validates token, deletes from Redis)
        sso_data = await sso_auth_service.consume_sso_session(sso_token)

        # Use SSO data as fallback for names
        effective_first_name = first_name or sso_data.get("first_name")
        effective_last_name = last_name or sso_data.get("last_name")
        email = sso_data["email"]

        # 2. Create owner user without password, skip verification email
        owner_user = await user_service.create_user(
            session=session,
            email=email,
            password=None,
            language_id=language_id,
            send_verification_email=False,
            first_name=effective_first_name,
            last_name=effective_last_name,
            gender_id=gender_id
        )

        # 3. Mark email as validated (provider already verified it)
        owner_user.email_address.validated_at = now_utc()

        # 4. Create client with owner
        client = cls.entity_class(
            name=client_name,
            owner_id=owner_user.id
        )
        session.add(client)
        await session.flush()
        await session.refresh(client)

        # 5. Associate owner with client
        owner_user.client_id = client.id
        await session.flush()

        # 6. Create SSO link
        await sso_link_service.create_link(
            user_id=owner_user.id,
            provider=sso_data["provider"],
            external_user_id=sso_data["external_user_id"],
            external_email=email,
            session=session
        )

        return client

    @classmethod
    async def user_is_client_owner(
            cls,
            user_id: str,
            session: AsyncSession
    ) -> bool:
        """
        Check if user is owner of at least one client.

        Args:
            user_id: The user ID
            session: Database session

        Returns:
            True if user is owner of at least one client
        """
        stmt = (
            select(cls.entity_class)
            .where(cls.entity_class.owner_id == user_id)
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None