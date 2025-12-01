"""
License rule entity definitions.

LicenseRule defines the types of constraints that can be applied to license plans:
- Quotas (e.g., MAX_USERS, MAX_PROJECTS_PER_MONTH)
- Feature toggles (e.g., EXPORT_PDF_ACCESS, API_ACCESS)
"""

from lys.core.entities import ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class LicenseRule(ParametricEntity):
    """
    Rule definition for license constraints.

    The id serves as both the primary key and the validator key.
    For example, a rule with id="MAX_USERS" will use the validator
    registered under "MAX_USERS" in the rule validators registry.

    Attributes:
        id: Rule identifier, also used as validator key (e.g., "MAX_USERS", "EXPORT_PDF_ACCESS")
        description: Human-readable description for UI/admin
        enabled: If False, rule is not enforced

    Rule Types:
        - Quota rules: Have a numeric limit_value in LicensePlanVersionRule (e.g., MAX_USERS=50)
        - Feature toggles: Presence in LicensePlanVersionRule means enabled, limit_value is NULL
    """
    __tablename__ = "license_rule"