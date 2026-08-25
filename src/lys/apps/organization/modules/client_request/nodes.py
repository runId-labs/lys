"""
GraphQL nodes for the client_request module.
"""
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.organization.modules.client_request.entities import ClientRequest
from lys.apps.organization.modules.client_request.services import (
    ClientRequestService,
    ClientRequestStatusService,
    ClientRequestTypeService,
)
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class ClientRequestTypeNode(EntityNode[ClientRequestTypeService], relay.Node):
    """GraphQL node for the ClientRequestType parametric entity."""
    id: relay.NodeID[str]
    enabled: bool
    description: Optional[str]


@register_node()
class ClientRequestStatusNode(EntityNode[ClientRequestStatusService], relay.Node):
    """GraphQL node for the ClientRequestStatus parametric entity."""
    id: relay.NodeID[str]
    enabled: bool
    description: Optional[str]


@register_node()
class ClientRequestNode(EntityNode[ClientRequestService], relay.Node):
    """GraphQL node for the ClientRequest entity.

    `details` is exposed as-is: its shape belongs to the application that declared the
    request type, and lys has no opinion on it.
    """
    id: relay.NodeID[str]
    client_id: str
    user_id: Optional[str]
    type_id: str
    status_id: str
    contact_phone: Optional[str]
    message: Optional[str]
    details: Optional[strawberry.scalars.JSON]
    reason_code: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[ClientRequest]

    @strawberry.field(description="What the client is asking for")
    async def type(self, info: Info) -> Optional[ClientRequestTypeNode]:
        return await self._lazy_load_relation("type", ClientRequestTypeNode, info)

    @strawberry.field(description="Lifecycle state (PENDING, PROCESSED, CANCELLED, ERROR)")
    async def status(self, info: Info) -> Optional[ClientRequestStatusNode]:
        return await self._lazy_load_relation("status", ClientRequestStatusNode, info)
