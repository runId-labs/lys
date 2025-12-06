"""
Fixtures for license rule definitions.

License rules define the types of constraints that can be applied to plans:
- Quota rules: MAX_USERS, MAX_PROJECTS_PER_MONTH
"""

from lys.apps.licensing.consts import (
    MAX_USERS,
    MAX_PROJECTS_PER_MONTH,
)
from lys.apps.licensing.modules.rule.services import LicenseRuleService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class LicenseRuleFixtures(EntityFixtures[LicenseRuleService]):
    """
    Fixtures for license rule definitions.

    These rules are used by LicensePlanVersionRule to define constraints for each plan version.
    The rule ID is also used as the key in the validators registry.
    """
    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": MAX_USERS,
            "attributes": {
                "enabled": True,
                "description": "Maximum number of users per subscription"
            }
        },
        {
            "id": MAX_PROJECTS_PER_MONTH,
            "attributes": {
                "enabled": True,
                "description": "Maximum number of projects that can be created per month"
            }
        },
    ]