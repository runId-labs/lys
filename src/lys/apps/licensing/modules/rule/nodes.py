"""
GraphQL nodes for license rules.
"""

from lys.apps.licensing.modules.rule.services import LicenseRuleService
from lys.core.graphql.nodes import parametric_node
from lys.core.registries import register_node


@register_node()
@parametric_node(LicenseRuleService)
class LicenseRuleNode:
    """
    GraphQL node for LicenseRule entity.

    Represents a rule definition for license constraints (quotas or feature toggles).
    """
    pass