from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.user.entities import User
from lys.apps.organization.modules.user.services import UserService
from lys.apps.user_auth.modules.user.consts import MALE_GENDER, FEMALE_GENDER
from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture(depends_on=["UserStatusFixtures", "GenderFixtures"])
class ClientRelatedUserDevFixtures(UserDevFixtures):
    """
    Development fixtures for additional Client-related users.

    Creates additional users for client organizations (non-owners).
    Owner users are created automatically by ClientDevFixtures via create_client_with_owner.
    Inherits formatting methods from UserDevFixtures.
    """
    _allowed_envs = [EnvironmentEnum.DEV]
    delete_previous_data = False

    data_list = [
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
class ClientUserDevFixtures(EntityFixtures[UserService]):
    """
    Development fixtures for assigning users to client organizations.

    Updates User.client_id to associate users with organizations
    and creates ClientUserRole entries for organization roles.
    """
    model = EntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV]
    delete_previous_data = False

    data_list = [
        # ACME Corporation users
        {
            "attributes": {
                "client_name": "ACME Corporation",
                "user_email": "user-acme-john@lys-test.fr",
                "role_codes": ["USER_ADMIN_ROLE"]
            }
        },
        {
            "attributes": {
                "client_name": "ACME Corporation",
                "user_email": "user-acme-jane@lys-test.fr",
                "role_codes": []
            }
        },
        # Tech Solutions Inc users
        {
            "attributes": {
                "client_name": "Tech Solutions Inc",
                "user_email": "user-tech-bob@lys-test.fr",
                "role_codes": ["USER_ADMIN_ROLE"]
            }
        },
        # Global Services Ltd users
        {
            "attributes": {
                "client_name": "Global Services Ltd",
                "user_email": "user-global-alice@lys-test.fr",
                "role_codes": []
            }
        }
    ]

    @classmethod
    async def create_from_service(
        cls,
        attributes: dict,
        session: AsyncSession
    ) -> User:
        """
        Assign a user to a client organization.

        This updates the user's client_id and creates ClientUserRole entries.

        Args:
            attributes: Dict containing:
                - client_name: Name of the client organization
                - user_email: Email of the user to assign
                - role_codes: List of role codes to assign

        Returns:
            User: The updated user entity
        """
        # Get client by name
        client_entity = cls.app_manager.get_entity("client")
        stmt = select(client_entity).where(client_entity.name == attributes["client_name"])
        result = await session.execute(stmt)
        client = result.scalar_one_or_none()

        if client is None:
            raise ValueError(f"Client with name '{attributes['client_name']}' not found. "
                           f"Make sure ClientDevFixtures has been loaded first.")

        # Get user by email
        user_service = cls.app_manager.get_service("user")
        user = await user_service.get_by_email(email=attributes["user_email"], session=session)

        if user is None:
            raise ValueError(f"User with email '{attributes['user_email']}' not found. "
                           f"Make sure ClientRelatedUserDevFixtures has been loaded first.")

        # Set client_id on user
        user.client_id = client.id
        await session.flush()

        # Create ClientUserRole entries
        role_codes = attributes.get("role_codes", [])
        if role_codes:
            client_user_role_entity = cls.app_manager.get_entity("client_user_role")
            for role_code in role_codes:
                client_user_role = client_user_role_entity(
                    user_id=user.id,
                    role_id=role_code
                )
                session.add(client_user_role)

        return user