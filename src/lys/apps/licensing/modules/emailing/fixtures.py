from lys.apps.licensing.consts import LICENSE_ADMIN_ROLE
from lys.apps.licensing.modules.emailing.consts import (
    LICENSE_GRANTED_EMAILING_TYPE,
    LICENSE_REVOKED_EMAILING_TYPE,
    SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE,
    SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE,
    SUBSCRIPTION_CANCELED_EMAILING_TYPE,
)
from lys.apps.user_role.modules.emailing.fixtures import (
    EmailingTypeFixtures as BaseEmailingTypeFixtures,
)
from lys.core.registries import register_fixture


@register_fixture(depends_on=["RoleFixtures"])
class EmailingTypeFixtures(BaseEmailingTypeFixtures):

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
                    "currency": None,
                    "billing_period": None,
                    "next_billing_date": None,
                },
                "roles": [LICENSE_ADMIN_ROLE]
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
                    "currency": None,
                    "error_reason": None,
                },
                "roles": [LICENSE_ADMIN_ROLE]
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
                },
                "roles": [LICENSE_ADMIN_ROLE]
            }
        }
    ]