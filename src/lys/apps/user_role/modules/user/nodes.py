from datetime import datetime
from typing import Optional, List, Dict, Any

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay

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
from lys.core.registers import register_node

@register_node()
class UserNode(EntityNode[UserService], relay.Node):
    """
    Extended user node with role information.

    This node extends the base UserNode from user_auth by adding the list
    of roles assigned to the user. It overrides the user_auth UserNode when
    the user_role app is enabled.
    """
    id: relay.NodeID[str]
    email_address: "UserEmailAddressNode"
    status: "UserStatusNode"
    language: "LanguageNode"
    private_data: Optional["UserPrivateDataNode"]
    roles: List["RoleNode"]
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: User):
        # Get effective nodes to support overriding
        effective_email_node = UserEmailAddressNode.get_effective_node()
        effective_status_node = UserStatusNode.get_effective_node()
        effective_language_node = LanguageNode.get_effective_node()
        effective_private_data_node = UserPrivateDataNode.get_effective_node()
        effective_role_node = RoleNode.get_effective_node()

        return cls(
            id=entity.id,
            email_address=effective_email_node.from_obj(entity.email_address),
            status=effective_status_node.from_obj(entity.status),
            language=effective_language_node.from_obj(entity.language),
            private_data=effective_private_data_node.from_obj(entity.private_data) if entity.private_data else None,
            roles=[effective_role_node.from_obj(role) for role in entity.roles] if entity.roles else [],
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

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