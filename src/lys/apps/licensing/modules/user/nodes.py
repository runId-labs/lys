"""
GraphQL nodes for licensing user module.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.base.modules.language.nodes import LanguageNode
from lys.apps.organization.modules.client.nodes import ClientNode
from lys.apps.organization.modules.user.entities import User
from lys.apps.organization.modules.user.services import UserService
from lys.apps.user_auth.modules.user.nodes import (
    UserEmailAddressNode,
    UserStatusNode,
    UserPrivateDataNode
)
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node
from lys.core.utils.manager import classproperty


@register_node()
class UserNode(EntityNode[UserService], relay.Node):
    """
    Extended user node with client organization, role, and licensing information.

    This node extends the organization UserNode by adding:
    - is_licensed: Whether the user has a license (is in subscription_user table)

    It overrides the organization UserNode when the licensing app is enabled.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
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

    @strawberry.field(description="User email address")
    async def email_address(self, info: Info) -> UserEmailAddressNode:
        """Get the user's email address."""
        return await self._lazy_load_relation('email_address', UserEmailAddressNode, info)

    @strawberry.field(description="User status")
    async def status(self, info: Info) -> UserStatusNode:
        """Get the user's status."""
        return await self._lazy_load_relation('status', UserStatusNode, info)

    @strawberry.field(description="User preferred language")
    async def language(self, info: Info) -> LanguageNode:
        """Get the user's preferred language."""
        return await self._lazy_load_relation('language', LanguageNode, info)

    @strawberry.field(description="User private data (GDPR protected)")
    async def private_data(self, info: Info) -> Optional[UserPrivateDataNode]:
        """Get the user's private data (nullable)."""
        return await self._lazy_load_relation('private_data', UserPrivateDataNode, info)

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

    @strawberry.field(description="Whether this user has a license (is associated with a subscription)")
    async def is_licensed(self, info: Info) -> bool:
        """
        Check if this user has a license.

        A user is considered licensed if they are associated with
        any subscription in the subscription_user table.

        Args:
            info: GraphQL context containing the database session

        Returns:
            bool: True if the user has a license
        """
        subscription_service = info.context.app_manager.get_service("subscription")
        session = info.context.session
        return await subscription_service.is_user_licensed(self._entity.id, session)

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        """
        Define allowed order by keys for User queries.

        Allowed sorting fields:
        - created_at: User creation date
        - email_address: User email address (requires join with user_email_address)
        - first_name: User first name (requires join with user_private_data)
        - last_name: User last name (requires join with user_private_data)

        Note: The query using these order_by fields MUST include the necessary joins.
        """
        entity_class = self.service_class.entity_class
        email_entity = self.service_class.app_manager.get_entity("user_email_address")
        private_data_entity = self.service_class.app_manager.get_entity("user_private_data")

        return {
            "created_at": entity_class.created_at,
            "email_address": email_entity.id,
            "first_name": private_data_entity.first_name,
            "last_name": private_data_entity.last_name,
        }