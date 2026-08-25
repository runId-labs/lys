from datetime import datetime
from typing import Any, Dict, Optional

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay

from lys.apps.organization.modules.client.entities import Client
from lys.apps.organization.modules.client.services import ClientService
from lys.apps.organization.modules.client_request.nodes import ClientRequestNode
from lys.core.contexts import Info
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class ClientNode(EntityNode[ClientService], relay.Node):
    """
    GraphQL node for Client entity.

    Represents a client organization with an owner user.
    """
    id: relay.NodeID[str]
    name: str
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[Client]

    @strawberry.field
    def owner_id(self) -> relay.GlobalID:
        return relay.GlobalID("UserNode", self._entity.owner_id)

    @strawberry.field(
        description="Requests from this client still waiting for an action, oldest first"
    )
    async def open_requests(self, info: Info) -> list[ClientRequestNode]:
        """What this client is waiting on.

        Returns the rows rather than a count: a listing wants a number in a column and
        the reasons behind it on hover, and both come from the same query. Settled
        requests are left out — they call for nothing.
        """
        service = info.context.app_manager.get_service("client_request")
        requests = await service.get_open_for_client(self._entity.id, info.context.session)

        return [ClientRequestNode.from_obj(request) for request in requests]

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "created_at": self.entity_class.created_at,
            "updated_at": self.entity_class.updated_at,
            "name": self.entity_class.name
        }
