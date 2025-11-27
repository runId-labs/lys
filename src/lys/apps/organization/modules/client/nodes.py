from datetime import datetime
from typing import Any, Dict, Optional

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay

from lys.apps.organization.modules.client.entities import Client
from lys.apps.organization.modules.client.services import ClientService
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

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "created_at": self.entity_class.created_at,
            "updated_at": self.entity_class.updated_at,
            "name": self.entity_class.name
        }
