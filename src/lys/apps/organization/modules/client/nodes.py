from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.organization.modules.client.entities import Client
from lys.apps.organization.modules.client.services import ClientService
from lys.core.graphql.nodes import EntityNode
from lys.core.registers import register_node


@register_node()
class ClientNode(EntityNode[ClientService], relay.Node):
    """
    GraphQL node for Client entity.

    Represents a client organization with an owner user.
    """
    id: relay.NodeID[str]
    name: str
    owner_id: str
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: Client) -> "ClientNode":
        """
        Convert a Client entity to a ClientNode.

        Args:
            entity: The Client entity to convert

        Returns:
            ClientNode instance
        """
        return cls(
            id=entity.id,
            name=entity.name,
            owner_id=entity.owner_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )