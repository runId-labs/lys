from lys.apps.base.modules.emailing.consts import (
    WAITING_EMAILING_STATUS,
    SENT_EMAILING_STATUS,
    ERROR_EMAILING_STATUS
)
from lys.apps.base.modules.emailing.services import EmailingStatusService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class EmailingStatusFixtures(EntityFixtures[EmailingStatusService]):

    model = ParametricEntityFixturesModel
    data_list = [
        {
            "id": WAITING_EMAILING_STATUS,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": SENT_EMAILING_STATUS,
            "attributes": {
                "enabled": True
            }
        },
        {
            "id": ERROR_EMAILING_STATUS,
            "attributes": {
                "enabled": True
            }
        }
    ]
