from datetime import datetime
from typing import Optional, List

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.organization.modules.client.nodes import ClientNode
from lys.apps.organization.modules.user.entities import ClientUser
from lys.apps.organization.modules.user.services import ClientUserService
from lys.apps.user_auth.modules.user.nodes import UserNode
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.core.graphql.nodes import EntityNode
from lys.core.registers import register_node


@register_node()
class ClientUserNode(EntityNode[ClientUserService], relay.Node):
    """
    GraphQL node for ClientUser entity.

    Represents the many-to-many relationship between Client and User.
    Provides lazy-loaded access to both the user and client information.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[ClientUser]

    @strawberry.field(description="The user associated with this client relationship")
    async def user(self, info: Info) -> UserNode:
        """
        Get the user associated with this client relationship.

        Args:
            info: GraphQL context containing the database session

        Returns:
            UserNode: The user node
        """
        return await self._lazy_load_relation('user', UserNode, info)

    @strawberry.field(description="The client organization")
    async def client(self, info: Info) -> ClientNode:
        """
        Get the client (organization) associated with this user relationship.

        Args:
            info: GraphQL context containing the database session

        Returns:
            ClientNode: The client node
        """
        return await self._lazy_load_relation('client', ClientNode, info)

    @strawberry.field(description="The roles assigned to this user in the client organization")
    async def roles(self, info: Info) -> List[RoleNode]:
        """
        Get the roles assigned to this user in the client organization.

        This resolver handles nested relationships by loading client_user_roles first,
        then loading the role for each client_user_role.

        Args:
            info: GraphQL context containing the database session

        Returns:
            List[RoleNode]: List of role nodes
        """
        if not hasattr(self, '_entity'):
            return []

        # Get session from context
        session = info.context.session

        # Load the client_user_roles relationship
        await session.refresh(self._entity, ['client_user_roles'])

        # Load the role for each client_user_role and convert to nodes
        result = []
        for client_user_role in self._entity.client_user_roles:
            await session.refresh(client_user_role, ['role'])
            if client_user_role.role is not None:
                result.append(RoleNode.get_effective_node().from_obj(client_user_role.role))

        return result