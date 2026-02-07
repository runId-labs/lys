from lys.apps.licensing.modules.emailing.consts import (
    LICENSE_GRANTED_EMAILING_TYPE,
    LICENSE_REVOKED_EMAILING_TYPE,
    SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE,
    SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE,
    SUBSCRIPTION_CANCELED_EMAILING_TYPE,
)
from lys.apps.base.modules.emailing.services import EmailingTypeService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class EmailingTypeFixtures(EntityFixtures[EmailingTypeService]):

    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {
            "id": LICENSE_GRANTED_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "license granted",
                "template": "license_granted",
                "context_description": {
                    "front_url": None,
                    "license_name": None,
                    "client_name": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        },
        {
            "id": LICENSE_REVOKED_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "license revoked",
                "template": "license_revoked",
                "context_description": {
                    "front_url": None,
                    "license_name": None,
                    "client_name": None,
                    "reason": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        },
        {
            "id": SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "subscription payment successful",
                "template": "subscription_payment_success",
                "context_description": {
                    "front_url": None,
                    "client_name": None,
                    "plan_name": None,
                    "amount": None,
                    "billing_period": None,
                    "next_billing_date": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        },
        {
            "id": SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "subscription payment failed",
                "template": "subscription_payment_failed",
                "context_description": {
                    "front_url": None,
                    "client_name": None,
                    "plan_name": None,
                    "amount": None,
                    "error_reason": None,
                    "retry_url": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        },
        {
            "id": SUBSCRIPTION_CANCELED_EMAILING_TYPE,
            "attributes": {
                "enabled": True,
                "subject": "subscription canceled",
                "template": "subscription_canceled",
                "context_description": {
                    "front_url": None,
                    "client_name": None,
                    "plan_name": None,
                    "effective_date": None,
                    "user": [{"private_data": ["first_name", "last_name", "gender_id"]}]
                }
            }
        }
    ]