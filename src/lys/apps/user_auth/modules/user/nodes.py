from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.user_auth.modules.user.entities import UserEmailAddress, User, UserOneTimeToken, UserPrivateData
from lys.apps.user_auth.modules.user.services import (
    UserStatusService,
    GenderService,
    UserEmailAddressService,
    UserService,
    UserOneTimeTokenService,
    UserPrivateDataService
)
from lys.core.contexts import Info
from lys.core.graphql.nodes import parametric_node, EntityNode, ServiceNode
from lys.core.registers import register_node


@register_node()
@parametric_node(UserStatusService)
class UserStatusNode:
    pass


@register_node()
@parametric_node(GenderService)
class GenderNode:
    pass


@strawberry.type
@register_node()
class UserEmailAddressNode(EntityNode[UserEmailAddressService], relay.Node):
    id: relay.NodeID[str]
    address: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: UserEmailAddress) -> "UserEmailAddressNode":
        return cls(
            id=entity.id,
            address=entity.address,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


@strawberry.type
@register_node()
class UserNode(EntityNode[UserService], relay.Node):
    id: relay.NodeID[str]
    email_address: UserEmailAddressNode
    status: UserStatusNode
    private_data: Optional["UserPrivateDataNode"]
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: User):
        return cls(
            id=entity.id,
            email_address=UserEmailAddressNode.from_obj(entity.email_address),
            status=UserStatusNode.from_obj(entity.status),
            private_data=UserPrivateDataNode.from_obj(entity.private_data) if entity.private_data else None,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


@strawberry.type
@register_node()
class UserPrivateDataNode(EntityNode[UserPrivateDataService], relay.Node):
    """
    GDPR-protected user private data node.

    Only accessible by:
    - The user themselves (via OWNER access level)
    - Super users

    Returns None if data has been anonymized.
    """
    id: relay.NodeID[str]
    first_name: Optional[str]
    last_name: Optional[str]
    gender: Optional[GenderNode]
    created_at: datetime
    updated_at: Optional[datetime]
    anonymized_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: UserPrivateData) -> "UserPrivateDataNode":
        return cls(
            id=entity.id,
            first_name=entity.first_name,
            last_name=entity.last_name,
            gender=GenderNode.from_obj(entity.gender) if entity.gender else None,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            anonymized_at=entity.anonymized_at,
        )


@strawberry.type
@register_node()
class UserOneTimeTokenNode(EntityNode[UserOneTimeTokenService], relay.Node):
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    used_at: Optional[datetime]
    status_id: str
    type_id: str
    user: UserNode

    @classmethod
    def from_obj(cls, entity: UserOneTimeToken) -> "UserOneTimeTokenNode":
        return cls(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            used_at=entity.used_at,
            status_id=entity.status_id,
            type_id=entity.type_id,
            user=UserNode.from_obj(entity.user),
        )


@strawberry.type
@register_node()
class ForgottenPasswordNode(ServiceNode[UserService]):
    success: bool


@strawberry.type
@register_node()
class ResetPasswordNode(ServiceNode[UserService]):
    success: bool

