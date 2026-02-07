"""
License application entity definition.

LicenseApplication defines the applications that can have their own license plans.
This supports multi-app licensing where a client can have separate subscriptions
for different applications (e.g., App A with PRO plan, App B with STARTER plan).
"""

from lys.core.entities import ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class LicenseApplication(ParametricEntity):
    """
    Application that can have its own license plans.

    Attributes:
        id: Application identifier (e.g., "DEFAULT", "APP_A", "APP_B")
        description: Human-readable description
        enabled: If False, application is not available for new subscriptions

    Usage:
        Each LicensePlan is associated with a LicenseApplication.
        This allows different applications to have different plan structures
        and a client can subscribe to multiple apps independently.
    """
    __tablename__ = "license_application"