from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS, LOGIN_BLOCKED_USER_STATUS
from lys.apps.user_auth.modules.user.models import UserFixturesModel
from lys.apps.user_auth.modules.user.services import UserService, UserStatusService
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


@register_fixture(depends_on=["UserStatusFixtures"])
class UserDevFixtures(EntityFixtures[UserService]):
    model = UserFixturesModel
    _allowed_envs = [EnvironmentEnum.DEV,]

    data_list = [
        {
            "attributes": {
                "email_address": "enabled_user@lys-test.fr",
                "password": "password",
            }
        },
        {
            "attributes": {
                "email_address": "disabled_user@lys-test.fr",
                "password": "password",
                "status_id": LOGIN_BLOCKED_USER_STATUS,
            }
        },
        {
            "attributes": {
                "email_address": "super_user@lys-test.fr",
                "password": "password",
                "is_super_user": True,
            }
        },
    ]

    @classmethod
    async def format_email_address(cls, email_address: str):
        user_email_address_class = cls.get_entity_by_name("user_email_address")
        return user_email_address_class(id=email_address)

    @classmethod
    async def format_password(cls, password: str) -> str:
        return AuthUtils.hash_password(password)