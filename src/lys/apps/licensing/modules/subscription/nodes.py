"""
GraphQL nodes for subscriptions.
"""

from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.licensing.modules.plan.nodes import (
    LicensePlanVersionNode,
    LicensePlanVersionPriceNode,
)
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

    @strawberry.field(description="Pending plan version for scheduled downgrade")
    async def pending_plan_version(self, info: Info) -> Optional[LicensePlanVersionNode]:
        if self._entity.pending_plan_version is None:
            return None
        return LicensePlanVersionNode.from_obj(self._entity.pending_plan_version)

    @strawberry.field(description="Whether a downgrade is scheduled")
    def has_pending_downgrade(self) -> bool:
        return self._entity.has_pending_downgrade

    @strawberry.field(description="Whether this is a free subscription (no payment provider)")
    def is_free(self) -> bool:
        return self._entity.provider_subscription_id is None

    @strawberry.field(description="The price subscribed to, carrying periodicity, currency and commitment")
    async def plan_version_price(self, info: Info) -> Optional[LicensePlanVersionPriceNode]:
        if self._entity.plan_version_price is None:
            return None
        return LicensePlanVersionPriceNode.from_obj(self._entity.plan_version_price)

    @strawberry.field(description="End of the contractual commitment, null when not committed")
    def commitment_end_date(self) -> Optional[datetime]:
        return self._entity.commitment_end_date

    @strawberry.field(description="Whether the client is still bound by a commitment")
    def is_committed(self) -> bool:
        return self._entity.is_committed

    @strawberry.field(
        description="Last date a cancellation is accepted for the current term; "
                    "past it the commitment is tacitly renewed"
    )
    def notice_deadline(self) -> Optional[datetime]:
        return self._entity.notice_deadline

    @strawberry.field(description="Whether a cancellation can still be requested for this term")
    def can_be_cancelled_now(self) -> bool:
        return self._entity.is_within_notice_period

    @strawberry.field(description="Date a scheduled plan change takes effect")
    def effective_change_date(self) -> Optional[datetime]:
        return self._entity.effective_change_date
