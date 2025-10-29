from lys.apps.user_auth.modules.auth.consts import FAILED_LOGIN_ATTEMPT_STATUS, SUCCEED_LOGIN_ATTEMPT_STATUS
from lys.apps.user_auth.modules.auth.services import LoginAttemptStatusService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class LoginAttemptStatusFixtures(EntityFixtures[LoginAttemptStatusService]):
    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": FAILED_LOGIN_ATTEMPT_STATUS,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": SUCCEED_LOGIN_ATTEMPT_STATUS,
            "attributes": {
                "enabled": True
            }
        }
    ]