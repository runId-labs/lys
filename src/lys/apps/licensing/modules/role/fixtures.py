"""
Role fixtures for licensing app.

Defines the LICENSE_ADMIN_ROLE with access to subscription management webservices.
"""

from lys.apps.licensing.consts import LICENSE_ADMIN_ROLE
from lys.apps.user_role.modules.role.fixtures import RoleFixtures
from lys.core.registries import register_fixture


LICENSE_ADMIN_ROLE_WEBSERVICES = [
    "all_clients",
    "client",
    "subscription",
    "create_checkout_session",
    "create_billing_portal_session",
    "add_client_user_to_subscription",
    "remove_client_user_from_subscription",
    # Catalogue administration
    "all_license_plans",
    "all_license_plan_versions",
    # Read before write: a version is published with the rules that exist, not
    # with the ones the interface happens to know about
    "all_license_rules",
    "create_license_plan_version",
    "set_license_plan_version_rule",
    "set_license_plan_version_enabled",
    "all_license_discounts",
    "create_license_discount",
    "set_license_discount_enabled",
    # Manual billing, never opened to organization roles
    "subscribe_client_manually",
    "set_subscription_billing_mode",
    "revoke_subscription_discount",
    # Reading what a client signed belongs to the same act as granting a
    # discount against it: the operator must not have to remember, nor be able
    # to forget, what was agreed
    "all_client_legal_acceptances"
]


@register_fixture()
class LicensingRoleFixtures(RoleFixtures):
    """
    Fixtures for licensing-specific roles.

    Adds LICENSE_ADMIN_ROLE without deleting existing roles.
    """

    delete_previous_data = False

    data_list = [
        {
            "id": LICENSE_ADMIN_ROLE,
            "attributes": {
                "enabled": True,
                "description": "Administrator role with license and subscription management capabilities.",
                "role_webservices": LICENSE_ADMIN_ROLE_WEBSERVICES
            }
        }
    ]