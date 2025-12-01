"""
GraphQL nodes for license rules.
"""

from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.licensing.modules.rule.entities import LicenseRule
from lys.apps.licensing.modules.rule.services import LicenseRuleService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class LicenseRuleNode(EntityNode[LicenseRuleService], relay.Node):
    """
    GraphQL node for LicenseRule entity.

    Represents a rule definition for license constraints (quotas or feature toggles).
    """
    id: relay.NodeID[str]
    description: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicenseRule]