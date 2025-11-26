from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.client.services import ClientService
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture(depends_on=["ClientRelatedUserDevFixtures"])
class ClientDevFixtures(EntityFixtures[ClientService]):
    """
    Development fixtures for Client entities.

    Creates test client organizations with their owner users for development and testing.
    """

    model = EntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV,]

    data_list = [
        {
            "attributes": {
                "name": "ACME Corporation",
                "owner_id": "owner-acme@lys-test.fr"
                # "client_users": [
                #     {
                #         "user": {
                #             "email_address": "user-acme-john@lys-test.fr",
                #             "password": "password",
                #             "language_id": "fr",
                #             "private_data": {
                #                 "first_name": "John",
                #                 "last_name": "Doe",
                #                 "gender_id": MALE_GENDER
                #             }
                #         },
                #         "client_user_roles": [
                #             {
                #                 "role_id": USER_ADMIN_ROLE
                #             }
                #         ]
                #     },
                #     {
                #         "user": {
                #             "email_address": "user-acme-jane@lys-test.fr",
                #             "password": "password",
                #             "language_id": "fr",
                #             "private_data": {
                #                 "first_name": "Jane",
                #                 "last_name": "Williams",
                #                 "gender_id": FEMALE_GENDER
                #             }
                #         },
                #         "client_user_roles": []
                #     }
                # ]
            }
        },
        {
            "attributes": {
                "name": "Tech Solutions Inc",
                "owner_id": "owner-tech@lys-test.fr"
                # "client_users": [
                #     {
                #         "user": {
                #             "email_address": "user-tech-bob@lys-test.fr",
                #             "password": "password",
                #             "language_id": "fr",
                #             "private_data": {
                #                 "first_name": "Bob",
                #                 "last_name": "Taylor",
                #                 "gender_id": MALE_GENDER
                #             }
                #         },
                #         "client_user_roles": [
                #             {
                #                 "role_id": USER_ADMIN_ROLE
                #             }
                #         ]
                #     }
                # ]
            }
        },
        {
            "attributes": {
                "name": "Global Services Ltd",
                "owner_id": "owner-global@lys-test.fr"
                # "client_users": [
                #     {
                #         "user": {
                #             "email_address": "user-global-alice@lys-test.fr",
                #             "password": "password",
                #             "language_id": "fr",
                #             "private_data": {
                #                 "first_name": "Alice",
                #                 "last_name": "Martinez",
                #                 "gender_id": FEMALE_GENDER
                #             }
                #         },
                #         "client_user_roles": []
                #     }
                # ]
            }
        }
    ]

    @classmethod
    async def format_owner_id(cls, owner_id: str, session: AsyncSession) -> str:
        """
        Get existing owner user by email and return their ID.

        Args:
            owner_id: Email address of the owner user (temporary value)
            session: Database session

        Returns:
            str: The user's ID

        Raises:
            ValueError: If the owner user is not found
        """
        user_service = cls.app_manager.get_service("user")
        user = await user_service.get_by_email(email=owner_id, session=session)

        if user is None:
            raise ValueError(f"Owner user with email '{owner_id}' not found. "
                           f"Make sure OwnerUserDevFixtures has been loaded first.")

        return user.id

    # @classmethod
    # async def format_client_users(cls, client_users: list[dict], session: AsyncSession) -> list[ClientUser]:
    #     """
    #     Format client_users to create ClientUser entities.
    #
    #     Creates ClientUser entities with their users and roles.
    #     The client_id will be set automatically by SQLAlchemy relationship.
    #     """
    #     client_user_class = cls.app_manager.get_entity("client_user")
    #     user_class = cls.app_manager.get_entity("user")
    #     user_email_address_class = cls.app_manager.get_entity("user_email_address")
    #     user_private_data_class = cls.app_manager.get_entity("user_private_data")
    #     client_user_role_class = cls.app_manager.get_entity("client_user_role")
    #
    #     client_user_entities = []
    #
    #     for client_user_data in client_users:
    #         # Create user entity
    #         user_data = client_user_data["user"]
    #         email_address_entity = user_email_address_class(id=user_data["email_address"])
    #         private_data_entity = user_private_data_class(
    #             id=str(uuid4()),
    #             **user_data["private_data"]
    #         )
    #         user_entity = user_class(
    #             email_address=email_address_entity,
    #             password=AuthUtils.hash_password(user_data["password"]),
    #             language_id=user_data["language_id"],
    #             private_data=private_data_entity
    #         )
    #
    #         # Create client_user_role entities
    #         roles = []
    #         for role_data in client_user_data.get("client_user_roles", []):
    #             client_user_role = client_user_role_class(
    #                 role_id=role_data["role_id"]
    #             )
    #             roles.append(client_user_role)
    #
    #         # Create client_user entity
    #         client_user = client_user_class(
    #             user=user_entity,
    #             client_user_roles=roles
    #         )
    #         client_user_entities.append(client_user)
    #
    #     return client_user_entities