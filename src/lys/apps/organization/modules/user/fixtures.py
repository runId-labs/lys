from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.user.entities import ClientUser
from lys.apps.organization.modules.user.services import ClientUserService
from lys.apps.user_auth.modules.user.consts import MALE_GENDER, FEMALE_GENDER
from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture(depends_on=["UserStatusFixtures", "GenderFixtures"])
class ClientRelatedUserDevFixtures(UserDevFixtures):
    """
    Development fixtures for Client-related users.

    Creates both owner users and additional users for client organizations
    without deleting existing users.
    Inherits formatting methods from UserDevFixtures.
    """
    _allowed_envs = [EnvironmentEnum.DEV,]
    delete_previous_data = False

    data_list = [
        # ==================== OWNER USERS ====================
        {
            "attributes": {
                "email_address": "owner-acme@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "Robert",
                    "last_name": "Smith",
                    "gender_id": MALE_GENDER
                }
            }
        },
        {
            "attributes": {
                "email_address": "owner-tech@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "Sarah",
                    "last_name": "Johnson",
                    "gender_id": FEMALE_GENDER
                }
            }
        },
        {
            "attributes": {
                "email_address": "owner-global@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "Michael",
                    "last_name": "Brown",
                    "gender_id": MALE_GENDER
                }
            }
        },
        # ==================== ADDITIONAL CLIENT USERS ====================
        {
            "attributes": {
                "email_address": "user-acme-john@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender_id": MALE_GENDER
                }
            }
        },
        {
            "attributes": {
                "email_address": "user-acme-jane@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "Jane",
                    "last_name": "Williams",
                    "gender_id": FEMALE_GENDER
                }
            }
        },
        {
            "attributes": {
                "email_address": "user-tech-bob@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "Bob",
                    "last_name": "Taylor",
                    "gender_id": MALE_GENDER
                }
            }
        },
        {
            "attributes": {
                "email_address": "user-global-alice@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "private_data": {
                    "first_name": "Alice",
                    "last_name": "Martinez",
                    "gender_id": FEMALE_GENDER
                }
            }
        }
    ]


@register_fixture(depends_on=["ClientRelatedUserDevFixtures", "ClientDevFixtures"])
class ClientUserDevFixtures(EntityFixtures[ClientUserService]):
    """
    Development fixtures for ClientUser relationships.

    Creates relationships between clients and users, assigning users to organizations.
    """
    model = EntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV,]
    delete_previous_data = False

    data_list = [
        # ACME Corporation users
        {
            "attributes": {
                "client_id": "ACME Corporation",  # Will be converted to actual client ID
                "user_id": "user-acme-john@lys-test.fr",  # Will be converted to actual user ID
                "client_user_roles": ["USER_ADMIN_ROLE"]
            }
        },
        {
            "attributes": {
                "client_id": "ACME Corporation",
                "user_id": "user-acme-jane@lys-test.fr",
                "client_user_roles": []
            }
        },
        # Tech Solutions Inc users
        {
            "attributes": {
                "client_id": "Tech Solutions Inc",
                "user_id": "user-tech-bob@lys-test.fr",
                "client_user_roles": ["USER_ADMIN_ROLE"]
            }
        },
        # Global Services Ltd users
        {
            "attributes": {
                "client_id": "Global Services Ltd",
                "user_id": "user-global-alice@lys-test.fr",
                "client_user_roles": []
            }
        }
    ]

    @classmethod
    async def format_client_id(cls, client_id: str, session: AsyncSession) -> str:
        """
        Get existing client by name and return its ID.

        Args:
            client_id: Name of the client organization (temporary value)
            session: Database session

        Returns:
            str: The client's ID

        Raises:
            ValueError: If the client is not found
        """
        # Query client by name (client_id contains the name temporarily)
        from sqlalchemy import select
        client_entity = cls.app_manager.get_entity("client")
        stmt = select(client_entity).where(client_entity.name == client_id)
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()

        if client is None:
            raise ValueError(f"Client with name '{client_id}' not found. "
                           f"Make sure ClientDevFixtures has been loaded first.")

        return client.id

    @classmethod
    async def format_user_id(cls, user_id: str, session: AsyncSession) -> str:
        """
        Get existing user by email and return their ID.

        Args:
            user_id: Email address of the user (temporary value)
            session: Database session

        Returns:
            str: The user's ID

        Raises:
            ValueError: If the user is not found
        """
        user_service = cls.app_manager.get_service("user")
        user = await user_service.get_by_email(email=user_id, session=session)

        if user is None:
            raise ValueError(f"User with email '{user_id}' not found. "
                           f"Make sure ClientRelatedUserDevFixtures has been loaded first.")

        return user.id

    @classmethod
    async def format_client_user_roles(cls, client_user_roles: list[str], session: AsyncSession) -> list:
        """
        Create ClientUserRole entities from role IDs.

        Args:
            client_user_roles: List of role IDs
            session: Database session

        Returns:
            list: List of ClientUserRole entities
        """
        client_user_role_class = cls.app_manager.get_entity("client_user_role")
        role_entities = []

        for role_id in client_user_roles:
            role_entities.append(client_user_role_class(role_id=role_id))

        return role_entities