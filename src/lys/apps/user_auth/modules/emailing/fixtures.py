from lys.apps.user_auth.modules.emailing.consts import (
    USER_PASSWORD_RESET_EMAILING_TYPE,
    USER_EMAIL_VERIFICATION_EMAILING_TYPE
)
from lys.apps.base.modules.emailing.services import EmailingTypeService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registers import register_fixture


@register_fixture()
class EmailingTypeFixtures(EntityFixtures[EmailingTypeService]):

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": USER_PASSWORD_RESET_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "password reset",
                "template": "user_password_reset",
                "context_description": {
                    "front_url": None,
                    "token": None,
                    "lang": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        },
        {
            "id": USER_EMAIL_VERIFICATION_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "email verification",
                "template": "user_email_verification",
                "context_description": {
                    "front_url": None,
                    "token": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        }
    ]