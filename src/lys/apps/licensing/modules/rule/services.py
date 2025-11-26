"""
License rule services.

This module provides:
- LicenseRuleService: CRUD operations for license rules
"""
from lys.apps.licensing.modules.rule.entities import LicenseRule
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class LicenseRuleService(EntityService[LicenseRule]):
    """
    Service for managing license rules.

    License rules define constraints that can be applied to plans:
    - Quota rules: MAX_USERS, MAX_PROJECTS, etc.
    - Feature toggles: EXPORT_PDF_ACCESS, API_ACCESS, etc.

    The rule ID is used as the validator key in the validators registry.
    """
    pass