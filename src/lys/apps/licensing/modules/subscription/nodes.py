"""
GraphQL nodes for subscriptions.
"""

from datetime import datetime
from typing import Optional

import strawberry
from strawberry.scalars import JSON
from strawberry import relay
from strawberry.types import Info

from lys.apps.licensing.modules.discount.nodes import SubscriptionDiscountNode
from lys.apps.licensing.modules.plan.nodes import (
    LicensePlanVersionNode,
    LicensePlanVersionPriceNode,
)
from lys.apps.licensing.modules.subscription.entities import (
    LicenseBillingMode,
    Subscription,
)
from lys.apps.licensing.modules.subscription.services import (
    LicenseBillingModeService,
    SubscriptionService,
)
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class LicenseBillingModeNode(EntityNode[LicenseBillingModeService], relay.Node):
    """
    GraphQL node for LicenseBillingMode entity.

    Represents how a subscription is collected.
    """
    id: relay.NodeID[str]
    code: str
    description: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicenseBillingMode]


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

    @strawberry.field(description="Whether nothing is owed for this subscription")
    def is_free(self) -> bool:
        return self._entity.is_free

    @strawberry.field(description="How this subscription is collected")
    async def billing_mode(self, info: Info) -> LicenseBillingModeNode:
        return LicenseBillingModeNode.from_obj(self._entity.billing_mode)

    @strawberry.field(description="Whether collection happens outside the application")
    def is_manually_billed(self) -> bool:
        return self._entity.is_manually_billed

    @strawberry.field(
        description="Discount granted on this subscription, with the value as "
                    "granted — which can differ from the discount's current value"
    )
    async def granted_discount(self, info: Info) -> Optional[SubscriptionDiscountNode]:
        subscription_service = info.context.app_manager.get_service("subscription")
        granted = await subscription_service.get_granted_discount(
            self._entity, info.context.session
        )

        if granted is None:
            return None

        return SubscriptionDiscountNode.from_obj(granted)

    @strawberry.field(description="The price subscribed to, carrying periodicity, currency and commitment")
    async def plan_version_price(self, info: Info) -> Optional[LicensePlanVersionPriceNode]:
        if self._entity.plan_version_price is None:
            return None
        return LicensePlanVersionPriceNode.from_obj(self._entity.plan_version_price)

    @strawberry.field(
        description="Amount actually owed per period, in the price's minor units; "
                    "null when nothing is owed. Differs from the catalogue price "
                    "when a discount was granted"
    )
    def amount_due(self) -> Optional[int]:
        return self._entity.amount_due

    @strawberry.field(
        description="Snapshot of the commercial terms agreed to: plan, price, "
                    "discount, commitment. Reads on its own, without following "
                    "any reference"
    )
    def receipt(self) -> Optional[JSON]:
        return self._entity.receipt

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
