"""
GraphQL nodes for subscriptions.
"""

from datetime import datetime
from typing import Optional, List

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.licensing.modules.plan.nodes import LicensePlanNode, LicensePlanVersionNode
from lys.apps.licensing.modules.subscription.entities import Subscription
from lys.apps.licensing.modules.subscription.services import SubscriptionService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class SubscriptionNode(EntityNode[SubscriptionService], relay.Node):
    """
    GraphQL node for Subscription entity.

    Represents a client's subscription to a license plan.
    """
    id: relay.NodeID[str]
    stripe_subscription_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[Subscription]

    @strawberry.field(description="The client that owns this subscription")
    def client_id(self) -> relay.GlobalID:
        return relay.GlobalID("ClientNode", self._entity.client_id)

    @strawberry.field(description="The current plan version ID")
    def plan_version_id(self) -> relay.GlobalID:
        return relay.GlobalID("LicensePlanVersionNode", self._entity.plan_version_id)

    @strawberry.field(description="Pending plan version ID for scheduled downgrade")
    def pending_plan_version_id(self) -> Optional[relay.GlobalID]:
        if self._entity.pending_plan_version_id is None:
            return None
        return relay.GlobalID("LicensePlanVersionNode", self._entity.pending_plan_version_id)

    @strawberry.field(description="The current plan version")
    async def plan_version(self, info: Info) -> LicensePlanVersionNode:
        return LicensePlanVersionNode.from_obj(self._entity.plan_version)

    @strawberry.field(description="The license plan")
    async def plan(self, info: Info) -> LicensePlanNode:
        return LicensePlanNode.from_obj(self._entity.plan)

    @strawberry.field(description="Pending plan version for scheduled downgrade")
    async def pending_plan_version(self, info: Info) -> Optional[LicensePlanVersionNode]:
        if self._entity.pending_plan_version is None:
            return None
        return LicensePlanVersionNode.from_obj(self._entity.pending_plan_version)

    @strawberry.field(description="Whether a downgrade is scheduled")
    def has_pending_downgrade(self) -> bool:
        return self._entity.has_pending_downgrade

    @strawberry.field(description="Whether this is a free subscription (no Stripe)")
    def is_free(self) -> bool:
        return self._entity.stripe_subscription_id is None

    @strawberry.field(description="Number of users consuming license seats")
    async def user_count(self, info: Info) -> int:
        return len(self._entity.users)

    @strawberry.field(description="Client users consuming license seats")
    async def users(self, info: Info) -> List[relay.GlobalID]:
        return [
            relay.GlobalID("ClientUserNode", user.id)
            for user in self._entity.users
        ]