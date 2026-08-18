"""
GraphQL nodes for discounts.
"""

from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.licensing.modules.discount.entities import (
    LicenseDiscount,
    LicenseDiscountGrant,
    LicenseDiscountUnit,
    SubscriptionDiscount,
)
from lys.apps.licensing.modules.discount.services import (
    LicenseDiscountGrantService,
    LicenseDiscountService,
    LicenseDiscountUnitService,
    SubscriptionDiscountService,
)
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class LicenseDiscountUnitNode(EntityNode[LicenseDiscountUnitService], relay.Node):
    """
    GraphQL node for LicenseDiscountUnit entity.

    Says how a discount value is to be read.
    """
    id: relay.NodeID[str]
    code: str
    description: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicenseDiscountUnit]


@register_node()
class LicenseDiscountGrantNode(EntityNode[LicenseDiscountGrantService], relay.Node):
    """
    GraphQL node for LicenseDiscountGrant entity.

    Says who may offer a discount: the client during checkout, or an
    administrator subscribing on their behalf.
    """
    id: relay.NodeID[str]
    code: str
    description: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicenseDiscountGrant]


@register_node()
class LicenseDiscountNode(EntityNode[LicenseDiscountService], relay.Node):
    """
    GraphQL node for LicenseDiscount entity.

    A reduction the catalogue can offer on a subscription's price.
    """
    id: relay.NodeID[str]
    code: str
    description: Optional[str]
    enabled: bool
    value: int
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[LicenseDiscount]

    @strawberry.field(description="How the value is expressed")
    def unit(self) -> LicenseDiscountUnitNode:
        return LicenseDiscountUnitNode.from_obj(self._entity.unit)

    @strawberry.field(description="Who may offer this discount")
    def grant(self) -> LicenseDiscountGrantNode:
        return LicenseDiscountGrantNode.from_obj(self._entity.grant)


@register_node()
class SubscriptionDiscountNode(EntityNode[SubscriptionDiscountService], relay.Node):
    """
    GraphQL node for SubscriptionDiscount entity.

    The discount a subscription benefits from, with the value as granted — which
    can differ from the discount's current value, since a revision never rewrites
    what a client was granted.
    """
    id: relay.NodeID[str]
    value: int
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[SubscriptionDiscount]

    @strawberry.field(description="Discount granted")
    def discount(self) -> LicenseDiscountNode:
        return LicenseDiscountNode.from_obj(self._entity.discount)

    @strawberry.field(description="Unit the granted value is read in")
    def unit(self) -> LicenseDiscountUnitNode:
        return LicenseDiscountUnitNode.from_obj(self._entity.unit)
