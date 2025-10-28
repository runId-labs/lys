from sqlalchemy.util import classproperty

from lys.apps.base.modules.emailing.consts import FORGOTTEN_PASSWORD_EMAILING_TYPE, EMAIL_VALIDATION_EMAILING_TYPE, \
    UPDATE_EMAIL_WARNING_EMAILING_TYPE, USER_WELCOME_EMAILING_TYPE, WAITING_EMAILING_STATUS, SENT_EMAILING_STATUS, \
    ERROR_EMAILING_STATUS
from lys.apps.base.modules.emailing.services import EmailingTypeService, EmailingStatusService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class EmailingTypeFixtures(EntityFixtures[EmailingTypeService]):

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": FORGOTTEN_PASSWORD_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "forgotten password",
                "template": "forgotten_password",
                "context_description": {
                    "front_url": None,
                    "token": None,
                    "lang": None,
                }
            }
        },
        {
            "id": EMAIL_VALIDATION_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "email validation",
                "template": "email_validation",
                "context_description": {
                    "front_url": None,
                    "token": None
                }
            }
        },
        {
            "id": UPDATE_EMAIL_WARNING_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "update email warning",
                "template": "update_email_warning",
                "context_description": None
            }
        },
        {
            "id": USER_WELCOME_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "welcome",
                "template": "user_welcome",
                "context_description": {
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        },
    ]


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
