from typing import List, Optional

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.organization.modules.client.nodes import ClientNode
from lys.apps.organization.modules.user.entities import User
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.apps.user_role.modules.user.nodes import UserNode as UserRoleUserNode
from lys.core.registries import register_node


@register_node()
class UserNode(UserRoleUserNode):
    """
    Extended user node with client organization information.

    Adds, on top of the user_role UserNode:
    - client_id: The client organization ID (null for supervisors)
    - client: The client organization itself (null for supervisors)
    - organization_roles: Roles assigned via client_user_role table

    It overrides the user_role UserNode when the organization app is enabled.
    """
    _entity: strawberry.Private[User]

    @strawberry.field(description="Client organization ID (null for supervisors)")
    def client_id(self) -> Optional[relay.GlobalID]:
        """Return the client ID as a GlobalID for Relay compatibility."""
        if self._entity.client_id is None:
            return None
        return relay.GlobalID("ClientNode", self._entity.client_id)

    @strawberry.field(description="Client organization (null for supervisors)")
    async def client(self, info: Info) -> Optional[ClientNode]:
        """Get the client organization for this user."""
        if self._entity.client_id is None:
            return None
        return await self._lazy_load_relation('client', ClientNode, info)

    @strawberry.field(description="Roles assigned to this user (supervisor roles)")
    async def roles(self, info: Info) -> List[RoleNode]:
        """Get the list of supervisor roles assigned to this user."""
        return await self._lazy_load_relation_list('roles', RoleNode, info)

    @strawberry.field(description="Roles assigned to this user in their client organization")
    async def organization_roles(self, info: Info) -> List[RoleNode]:
        """
        Get the roles assigned to this user in their client organization.

        This resolver loads client_user_roles and extracts the role from each.
        Only applicable for client users (users with client_id set).

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
                result.append(RoleNode.from_obj(client_user_role.role))

        return result
