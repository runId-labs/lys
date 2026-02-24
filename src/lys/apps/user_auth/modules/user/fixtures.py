import logging
import secrets
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_auth.modules.user.consts import (
    ENABLED_USER_STATUS,
    DISABLED_USER_STATUS,
    REVOKED_USER_STATUS,
    MALE_GENDER,
    FEMALE_GENDER,
    OTHER_GENDER,
    DELETED_USER_STATUS,
    STATUS_CHANGE_LOG_TYPE,
    ANONYMIZATION_LOG_TYPE,
    OBSERVATION_LOG_TYPE
)
from lys.apps.user_auth.modules.user.entities import UserEmailAddress, UserPrivateData
from lys.apps.user_auth.modules.user.models import UserFixturesModel
from lys.apps.user_auth.modules.user.services import (
    UserService,
    UserStatusService,
    GenderService,
    UserAuditLogTypeService
)
from lys.apps.user_auth.utils import AuthUtils
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class UserStatusFixtures(EntityFixtures[UserStatusService]):
    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": ENABLED_USER_STATUS,
            "attributes": {
                "enabled": True,
                "description": "Active user who can log in and access the system normally."
            }
        },
        {
            "id": DISABLED_USER_STATUS,
            "attributes": {
                "enabled": True,
                "description": "Temporarily deactivated user. Cannot log in but account can be re-enabled."
            }
        },
        {
            "id": REVOKED_USER_STATUS,
            "attributes": {
                "enabled": True,
                "description": "Permanently banned user. Cannot log in and requires admin intervention to restore."
            }
        },
        {
            "id": DELETED_USER_STATUS,
            "attributes": {
                "enabled": True,
                "description": "Anonymized user for GDPR compliance. Personal data has been removed."
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
                "enabled": True,
                "description": "Male gender identity option for user profiles."
            }
        },
        {
            "id": FEMALE_GENDER,
            "attributes": {
                "enabled": True,
                "description": "Female gender identity option for user profiles."
            }
        },
        {
            "id": OTHER_GENDER,
            "attributes": {
                "enabled": True,
                "description": "Non-binary or other gender identity option for user profiles."
            }
        }
    ]


@register_fixture()
class UserAuditLogTypeFixtures(EntityFixtures[UserAuditLogTypeService]):
    """
    Fixtures for user audit log type parametric entity.

    Provides log types for user audit trail:
    - STATUS_CHANGE: Automatic log when user status changes
    - ANONYMIZATION: Automatic log when user is anonymized (GDPR)
    - OBSERVATION: Manual observation/note added by administrators
    """
    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": STATUS_CHANGE_LOG_TYPE,
            "attributes": {
                "enabled": True,
                "description": "Automatic audit entry when user status changes (enabled, disabled, revoked)."
            }
        },
        {
            "id": ANONYMIZATION_LOG_TYPE,
            "attributes": {
                "enabled": True,
                "description": "Automatic audit entry when user data is anonymized for GDPR compliance."
            }
        },
        {
            "id": OBSERVATION_LOG_TYPE,
            "attributes": {
                "enabled": True,
                "description": "Manual note or observation added by administrator about a user."
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
                "status_id": DISABLED_USER_STATUS,
                "language_id": "fr",
                "private_data": {
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "gender_id": FEMALE_GENDER
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
    async def format_password(cls, password: str, attributes: dict) -> str:
        """Generate a random password and return its bcrypt hash.

        The provided password is ignored — a cryptographically random
        password is generated to prevent default credentials in dev fixtures.
        The generated password is logged so developers can use the accounts.
        """
        generated = secrets.token_urlsafe(16)
        email = attributes.get("email_address", "unknown")
        logging.info(f"Dev fixture password for {email}: {generated}")
        return AuthUtils.hash_password(generated)

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