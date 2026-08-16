"""
Fixtures for subscription billing modes.
"""

from lys.apps.licensing.consts import MANUAL_BILLING, PROVIDER_BILLING
from lys.apps.licensing.modules.subscription.services import LicenseBillingModeService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class LicenseBillingModeFixtures(EntityFixtures[LicenseBillingModeService]):
    """
    Fixtures for the ways a subscription can be collected.

    Reference data loaded in every environment. Both modes are shipped because
    both are implemented: an application starting without a payment provider
    bills manually, and switches subscription by subscription as it adopts one.
    """
    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {
            "id": PROVIDER_BILLING,
            "attributes": {
                "enabled": True,
                "description": "Collected by the configured payment provider"
            }
        },
        {
            "id": MANUAL_BILLING,
            "attributes": {
                "enabled": True,
                "description": "Collected outside the application, typically by invoicing"
            }
        },
    ]
