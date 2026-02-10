"""
Development fixtures for Client entities with licensing.

Creates test client organizations with their owner users and FREE plan subscriptions.
"""
import logging
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.modules.client.entities import Client
from lys.apps.licensing.modules.client.services import ClientService
from lys.apps.user_auth.modules.user.consts import MALE_GENDER
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture(depends_on=["LicensePlanVersionDevFixtures"])
class ClientDevFixtures(EntityFixtures[ClientService]):
    """
    Development fixtures for Client entities.

    Creates test client organizations with their owner users for development and testing.
    Uses create_client_with_owner which automatically:
    - Creates the owner user
    - Creates the client with owner_id set
    - Assigns FREE plan subscription
    """

    model = EntityFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV]

    data_list = [
        {
            "attributes": {
                "name": "ACME Corporation",
                "owner_email": "owner-acme@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "first_name": "Robert",
                "last_name": "Smith",
                "gender_id": MALE_GENDER,
            }
        },
        {
            "attributes": {
                "name": "Tech Solutions Inc",
                "owner_email": "owner-tech@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "first_name": "Alice",
                "last_name": "Johnson",
                "gender_id": None,
            }
        },
        {
            "attributes": {
                "name": "Global Services Ltd",
                "owner_email": "owner-global@lys-test.fr",
                "password": "password",
                "language_id": "fr",
                "first_name": "John",
                "last_name": "Doe",
                "gender_id": MALE_GENDER,
            }
        }
    ]

    @classmethod
    async def create_from_service(
        cls,
        attributes: dict,
        session: AsyncSession
    ) -> Client:
        """
        Create client with owner using the service method.

        This creates the full client setup including:
        - Owner user with private data
        - Client entity with owner_id set
        - FREE plan subscription
        """
        password = secrets.token_urlsafe(16)
        logging.info(f"Dev fixture password for {attributes['owner_email']}: {password}")

        return await cls.service.create_client_with_owner(
            session=session,
            client_name=attributes["name"],
            email=attributes["owner_email"],
            password=password,
            language_id=attributes["language_id"],
            first_name=attributes.get("first_name"),
            last_name=attributes.get("last_name"),
            gender_id=attributes.get("gender_id"),
            send_verification_email=False,
        )