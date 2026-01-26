"""
GraphQL nodes for licensing user module.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.organization.modules.client.nodes import ClientNode
from lys.apps.organization.modules.user.entities import ClientUser
from lys.apps.organization.modules.user.services import ClientUserService
from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node
from lys.core.utils.manager import classproperty


@register_node()
class ClientUserNode(EntityNode[ClientUserService], relay.Node):
    """
    ClientUserNode with licensing information.

    Extends the base ClientUser entity with is_licensed field.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[ClientUser]

    @strawberry.field(description="The user associated with this client relationship")
    async def user(self, info: Info) -> UserNode:
        """Get the user associated with this client relationship."""
        return await self._lazy_load_relation('user', UserNode, info)

    @strawberry.field(description="The client organization")
    async def client(self, info: Info) -> ClientNode:
        """Get the client (organization) associated with this user relationship."""
        return await self._lazy_load_relation('client', ClientNode, info)

    @strawberry.field(description="The roles assigned to this user in the client organization")
    async def roles(self, info: Info) -> List[RoleNode]:
        """Get the roles assigned to this user in the client organization."""
        if not hasattr(self, '_entity'):
            return []

        session = info.context.session
        await session.refresh(self._entity, ['client_user_roles'])

        result = []
        for client_user_role in self._entity.client_user_roles:
            await session.refresh(client_user_role, ['role'])
            if client_user_role.role is not None:
                result.append(RoleNode.from_obj(client_user_role.role))

        return result

    @strawberry.field(description="Whether this client user has a license (is associated with a subscription)")
    async def is_licensed(self, info: Info) -> bool:
        """
        Check if this client user has a license.

        A client user is considered licensed if they are associated with
        any subscription in the subscription_user table.

        Args:
            info: GraphQL context containing the database session

        Returns:
            bool: True if the user has a license
        """
        subscription_service = info.context.app_manager.get_service("subscription")
        session = info.context.session
        return await subscription_service.is_client_user_licensed(self._entity.id, session)

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        """
        Define allowed order by keys for ClientUser queries.

        Allowed sorting fields:
        - created_at: ClientUser creation date
        - email: User email address (requires join with user_email_address)
        - last_name: User last name (requires join with user_private_data)

        Note: The query using these order_by fields MUST include the necessary joins.
        """
        entity_class = self.service_class.entity_class
        email_entity = self.service_class.app_manager.get_entity("user_email_address")
        private_data_entity = self.service_class.app_manager.get_entity("user_private_data")

        return {
            "created_at": entity_class.created_at,
            "email": email_entity.id,
            "last_name": private_data_entity.last_name,
        }