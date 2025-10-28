"""
Fixtures for one-time token data.
"""

from lys.apps.base.modules.one_time_token.consts import (
    FORGOTTEN_PASSWORD_TOKEN_TYPE,
    PENDING_TOKEN_STATUS,
    USED_TOKEN_STATUS,
    REVOKED_TOKEN_STATUS
)
from lys.apps.base.modules.one_time_token.services import (
    OneTimeTokenTypeService,
    OneTimeTokenStatusService
)
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class OneTimeTokenTypeFixtures(EntityFixtures[OneTimeTokenTypeService]):
    """
    Fixtures for one-time token types.
    """
    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": FORGOTTEN_PASSWORD_TOKEN_TYPE,
            "attributes": {
                "enabled": True,
                "duration": 30  # 30 minutes - standard for password reset
            }
        }
    ]


@register_fixture()
class OneTimeTokenStatusFixtures(EntityFixtures[OneTimeTokenStatusService]):
    """
    Fixtures for one-time token statuses.
    """
    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": PENDING_TOKEN_STATUS,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": USED_TOKEN_STATUS,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": REVOKED_TOKEN_STATUS,
            "attributes": {
                "enabled": True
            }
        }
    ]