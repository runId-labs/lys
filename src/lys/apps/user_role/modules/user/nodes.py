from datetime import datetime
from typing import Optional, List, Dict, Any

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay
from strawberry.types import Info

from lys.apps.base.modules.language.nodes import LanguageNode
from lys.apps.user_auth.modules.user.nodes import (
    UserEmailAddressNode,
    UserStatusNode,
    UserPrivateDataNode
)
from lys.apps.user_role.modules.role.nodes import RoleNode
from lys.apps.user_role.modules.user.entities import User
from lys.apps.user_role.modules.user.services import UserService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node

@register_node()
class UserNode(EntityNode[UserService], relay.Node):
    """
    Extended user node with role information.

    This node extends the base UserNode from user_auth by adding the list
    of roles assigned to the user. It overrides the user_auth UserNode when
    the user_role app is enabled.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[User]

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

    @strawberry.field(description="Roles assigned to this user")
    async def roles(self, info: Info) -> List[RoleNode]:
        """Get the list of roles assigned to this user."""
        return await self._lazy_load_relation_list('roles', RoleNode, info)

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