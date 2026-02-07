"""
License application services.
"""

from lys.apps.licensing.modules.application.entities import LicenseApplication
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class LicenseApplicationService(EntityService[LicenseApplication]):
    """Service for license application operations."""

    service_name = "license_application"