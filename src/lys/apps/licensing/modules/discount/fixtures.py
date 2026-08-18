"""
Fixtures for the discount module.

Seeds how a discount's value is expressed and how it is obtained. No discount
itself is shipped: a reduction is a commercial decision, which belongs to the
application's offer.

Only one way of obtaining a discount is shipped — claiming it. A discount
applying on its own would raise a question no need has raised yet: what happens
when it meets a claimed one, since a subscription carries at most one.
"""

from lys.apps.licensing.consts import MANUAL_GRANT, PERCENT_UNIT
from lys.apps.licensing.modules.discount.services import (
    LicenseDiscountGrantService,
    LicenseDiscountUnitService,
)
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class LicenseDiscountUnitFixtures(EntityFixtures[LicenseDiscountUnitService]):
    """Units a discount value is read in. Reference data, loaded in every environment."""

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": PERCENT_UNIT,
            "attributes": {
                "enabled": True,
                "description": "Percentage taken off the price.",
            },
        },
    ]


@register_fixture()
class LicenseDiscountGrantFixtures(EntityFixtures[LicenseDiscountGrantService]):
    """Ways a discount is obtained. Reference data, loaded in every environment."""

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": MANUAL_GRANT,
            "attributes": {
                "enabled": True,
                "description": "Claimed by ticking it when subscribing."
            },
        },
    ]
