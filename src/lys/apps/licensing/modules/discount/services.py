"""
Services for the discount module.
"""

from lys.apps.licensing.modules.discount.entities import (
    LicenseDiscount,
    LicenseDiscountGrant,
    LicenseDiscountUnit,
    SubscriptionDiscount,
)
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class LicenseDiscountUnitService(EntityService[LicenseDiscountUnit]):
    """
    Service for managing how discount values are expressed.

    Units are reference data: they are provisioned by fixtures and referenced by
    discounts.
    """


@register_service()
class LicenseDiscountGrantService(EntityService[LicenseDiscountGrant]):
    """
    Service for managing how discounts are obtained.

    Grants are reference data: they are provisioned by fixtures and referenced
    by discounts.
    """


@register_service()
class LicenseDiscountService(EntityService[LicenseDiscount]):
    """
    Service for managing the discounts the catalogue offers.

    Discounts are declared by the application, either through fixtures or
    through the catalogue administration; this service only reads and writes
    them. Granting one to a subscription is the subscription service's job,
    since that is where the amount due is settled.
    """


@register_service()
class SubscriptionDiscountService(EntityService[SubscriptionDiscount]):
    """
    Service for the discount a subscription benefits from.
    """
