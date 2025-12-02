"""
GraphQL nodes for license plans and versions.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.licensing.modules.plan.entities import LicensePlan, LicensePlanVersion, LicensePlanVersionRule
from lys.apps.licensing.modules.plan.services import (
    LicensePlanService,
    LicensePlanVersionService,
    LicensePlanVersionRuleService,
)
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


if TYPE_CHECKING:
    from lys.apps.licensing.modules.rule.nodes import LicenseRuleNode


@register_node()
class LicensePlanVersionRuleNode(EntityNode[LicensePlanVersionRuleService], relay.Node):
    """
    GraphQL node for LicensePlanVersionRule entity.

    Represents the association between a plan version and a rule with its limit value.
    """
    id: relay.NodeID[str]
    limit_value: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicensePlanVersionRule]

    @strawberry.field(description="The rule ID")
    def rule_id(self) -> relay.GlobalID:
        return relay.GlobalID("LicenseRuleNode", self._entity.rule_id)

    @strawberry.field(description="The rule definition")
    async def rule(self, info: Info) -> "LicenseRuleNode":
        from lys.apps.licensing.modules.rule.nodes import LicenseRuleNode
        return LicenseRuleNode.from_obj(self._entity.rule)

    @strawberry.field(description="Whether this is a quota rule (has limit) or feature toggle")
    def is_quota(self) -> bool:
        return self._entity.limit_value is not None

    @strawberry.field(description="Whether this rule grants unlimited access (quota with no limit)")
    def is_unlimited(self) -> bool:
        return self._entity.limit_value is None


@register_node()
class LicensePlanVersionNode(EntityNode[LicensePlanVersionService], relay.Node):
    """
    GraphQL node for LicensePlanVersion entity.

    Represents a version of a license plan with pricing and rules.
    """
    id: relay.NodeID[str]
    version: int
    enabled: bool
    price_monthly: Optional[int]
    price_yearly: Optional[int]
    currency: str
    stripe_product_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicensePlanVersion]

    @strawberry.field(description="The parent license plan ID")
    def plan_id(self) -> relay.GlobalID:
        return relay.GlobalID("LicensePlanNode", self._entity.plan_id)

    @strawberry.field(description="The parent license plan")
    async def plan(self, info: Info) -> "LicensePlanNode":
        return LicensePlanNode.from_obj(self._entity.plan)

    @strawberry.field(description="Whether this is a free plan (no pricing)")
    def is_free(self) -> bool:
        return self._entity.is_free

    @strawberry.field(description="Rules associated with this version")
    async def rules(self, info: Info) -> List[LicensePlanVersionRuleNode]:
        return [LicensePlanVersionRuleNode.from_obj(rule) for rule in self._entity.rules]

    @strawberry.field(description="Monthly price formatted (e.g., '49.00 EUR')")
    def price_monthly_formatted(self) -> Optional[str]:
        if self._entity.price_monthly is None:
            return None
        amount = self._entity.price_monthly / 100
        return f"{amount:.2f} {self._entity.currency.upper()}"

    @strawberry.field(description="Yearly price formatted (e.g., '490.00 EUR')")
    def price_yearly_formatted(self) -> Optional[str]:
        if self._entity.price_yearly is None:
            return None
        amount = self._entity.price_yearly / 100
        return f"{amount:.2f} {self._entity.currency.upper()}"


@register_node()
class LicensePlanNode(EntityNode[LicensePlanService], relay.Node):
    """
    GraphQL node for LicensePlan entity.

    Represents a license plan type (FREE, STARTER, PRO, ENTERPRISE).
    """
    id: relay.NodeID[str]
    code: str
    description: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicensePlan]

    @strawberry.field(description="Client ID for custom plans (null for global plans)")
    def client_id(self) -> Optional[relay.GlobalID]:
        if self._entity.client_id is None:
            return None
        return relay.GlobalID("ClientNode", self._entity.client_id)

    @strawberry.field(description="Whether this is a custom plan for a specific client")
    def is_custom(self) -> bool:
        return self._entity.is_custom

    @strawberry.field(description="Current enabled version of this plan")
    async def current_version(self, info: Info) -> Optional[LicensePlanVersionNode]:
        version = self._entity.current_version
        if version is None:
            return None
        return LicensePlanVersionNode.from_obj(version)

    @strawberry.field(description="All versions of this plan")
    async def versions(self, info: Info) -> List[LicensePlanVersionNode]:
        return [LicensePlanVersionNode.from_obj(v) for v in self._entity.versions]