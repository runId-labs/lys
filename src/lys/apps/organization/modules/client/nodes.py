from datetime import datetime
from typing import Optional

import strawberry
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
    owner_id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[Client]
