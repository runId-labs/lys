from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.user.consts import (
    ENABLED_USER_STATUS,
    LOGIN_BLOCKED_USER_STATUS,
    MALE_GENDER,
    FEMALE_GENDER,
    OTHER_GENDER
)
from lys.apps.user_auth.modules.user.entities import UserEmailAddress, UserPrivateData
from lys.apps.user_auth.modules.user.models import UserFixturesModel
from lys.apps.user_auth.modules.user.services import UserService, UserStatusService, GenderService
from lys.apps.user_auth.utils import AuthUtils
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class UserStatusFixtures(EntityFixtures[UserStatusService]):
    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": ENABLED_USER_STATUS,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": LOGIN_BLOCKED_USER_STATUS,
            "attributes": {
                "enabled": True
            }
        }
    ]


@register_fixture()
class GenderFixtures(EntityFixtures[GenderService]):
    """
    Fixtures for gender parametric entity.

    Provides standard gender options for GDPR-protected user private data.
    """
    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": MALE_GENDER,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": FEMALE_GENDER,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": OTHER_GENDER,
            "attributes": {
                "enabled": True
            }
        }
    ]


@register_fixture(depends_on=["UserStatusFixtures", "GenderFixtures"])
class UserDevFixtures(EntityFixtures[UserService]):
    model = UserFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV,]

    data_list = [
        {
            "attributes": {
                "email_address": "enabled_user@lys-test.fr",
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
                "email_address": "disabled_user@lys-test.fr",
                "password": "password",
                "status_id": LOGIN_BLOCKED_USER_STATUS,
                "language_id": "fr",
                "private_data": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "gender_id": FEMALE_GENDER
                }
            }
        },
        {
            "attributes": {
                "email_address": "super_user@lys-test.fr",
                "password": "password",
                "is_super_user": True,
                "language_id": "fr",
                "private_data": {
                    "first_name": "Admin",
                    "last_name": "Super",
                    "gender_id": OTHER_GENDER
                }
            }
        },
    ]

    @classmethod
    async def format_email_address(cls, email_address: str, session: AsyncSession) -> UserEmailAddress:
        """
        Format email_address to create UserEmailAddress entity.

        Creates the entity instance without persisting it yet.
        The user_id will be set automatically by SQLAlchemy relationship
        when the User entity is persisted.
        """
        user_email_address_class = cls.app_manager.get_entity("user_email_address")
        return user_email_address_class(id=email_address)

    @classmethod
    async def format_password(cls, password: str) -> str:
        return AuthUtils.hash_password(password)

    @classmethod
    async def format_private_data(cls, private_data: dict, session: AsyncSession) -> UserPrivateData:
        """
        Format private_data to create UserPrivateData entity.

        Creates the entity instance without persisting it yet.
        The user_id will be set automatically by SQLAlchemy relationship
        when the User entity is persisted.

        Generates the ID explicitly to avoid SQLAlchemy UUID conflicts.
        """
        user_private_data_class = cls.app_manager.get_entity("user_private_data")
        return user_private_data_class(id=str(uuid4()), **private_data)