"""
GraphQL node for Client with licensing information.
"""

from typing import Optional

import strawberry
from strawberry.types import Info

from lys.apps.licensing.modules.client.entities import Client
from lys.apps.licensing.modules.plan.nodes import LicensePlanNode
from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode
from lys.apps.organization.modules.client.nodes import ClientNode as OrganizationClientNode
from lys.core.registries import register_node


@register_node()
class ClientNode(OrganizationClientNode):
    """
    Extended GraphQL node for Client with licensing information.

    Inherits id, name, created_at, updated_at, owner_id and open_requests from the
    organization ClientNode, and adds subscription and license plan fields.
    """
    _entity: strawberry.Private[Client]

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
