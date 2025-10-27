from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.user_auth.modules.user.entities import UserEmailAddress, User
from lys.apps.user_auth.modules.user.services import UserStatusService, UserEmailAddressService, UserService
from lys.core.graphql.nodes import parametric_node, EntityNode
from lys.core.registers import register_node


@register_node()
@parametric_node(UserStatusService)
class UserStatusNode:
    pass


@strawberry.type
@register_node()
class UserEmailAddressNode(EntityNode[UserEmailAddressService], relay.Node):
    id: relay.NodeID[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: UserEmailAddress) -> "UserEmailAddressNode":
        return cls(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


@strawberry.type
@register_node()
class UserNode(EntityNode[UserService], relay.Node):
    id: relay.NodeID[str]
    email_address: UserEmailAddressNode
    status: UserStatusNode
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: User):
        return cls(
            id=entity.id,
            email_address=UserEmailAddressNode.from_obj(entity.email_address),
            status=UserStatusNode.from_obj(entity.status),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )



