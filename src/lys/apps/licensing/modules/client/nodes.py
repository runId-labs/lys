"""
GraphQL node for Client with licensing information.
"""

from datetime import datetime
from typing import Any, Dict, Optional

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay
from strawberry.types import Info

from lys.apps.licensing.modules.client.entities import Client
from lys.apps.licensing.modules.plan.nodes import LicensePlanNode
from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode
from lys.apps.organization.modules.client.services import ClientService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class ClientNode(EntityNode[ClientService], relay.Node):
    """
    Extended GraphQL node for Client with licensing information.

    Adds subscription and license plan fields to the base ClientNode.
    """
    id: relay.NodeID[str]
    name: str
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[Client]

    @strawberry.field
    def owner_id(self) -> relay.GlobalID:
        return relay.GlobalID("UserNode", self._entity.owner_id)

    @strawberry.field(description="Current subscription for this client")
    async def subscription(self, info: Info) -> Optional[SubscriptionNode]:
        """Get the client's current subscription."""
        session = info.context.session
        subscription_service = self.service_class.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(
            self._entity.id, session
        )
        if subscription is None:
            return None

        return SubscriptionNode.from_obj(subscription)

    @strawberry.field(description="Current license plan for this client")
    async def license_plan(self, info: Info) -> Optional[LicensePlanNode]:
        """Get the client's current license plan."""
        session = info.context.session
        subscription_service = self.service_class.app_manager.get_service("subscription")
        subscription = await subscription_service.get_client_subscription(
            self._entity.id, session
        )
        if subscription is None:
            return None

        return LicensePlanNode.from_obj(subscription.plan)

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "created_at": self.entity_class.created_at,
            "updated_at": self.entity_class.updated_at,
            "name": self.entity_class.name
        }