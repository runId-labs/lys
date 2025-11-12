from datetime import datetime
from typing import Optional, Dict, Any

import strawberry
from strawberry import relay

from lys.apps.base.modules.language.nodes import LanguageNode
from lys.apps.user_auth.modules.user.entities import (
    UserEmailAddress,
    User,
    UserOneTimeToken,
    UserPrivateData,
    UserAuditLog
)
from lys.apps.user_auth.modules.user.services import (
    UserStatusService,
    GenderService,
    UserEmailAddressService,
    UserService,
    UserOneTimeTokenService,
    UserPrivateDataService,
    UserAuditLogTypeService,
    UserAuditLogService
)
from lys.core.graphql.nodes import parametric_node, EntityNode, ServiceNode
from lys.core.registers import register_node
from lys.core.utils.manager import classproperty


@register_node()
@parametric_node(UserStatusService)
class UserStatusNode:
    pass


@register_node()
@parametric_node(GenderService)
class GenderNode:
    pass


@register_node()
@parametric_node(UserAuditLogTypeService)
class UserAuditLogTypeNode:
    pass


@strawberry.type
@register_node()
class UserEmailAddressNode(EntityNode[UserEmailAddressService], relay.Node):
    id: relay.NodeID[str]
    address: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    validated_at: Optional[datetime]
    last_validation_request_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: UserEmailAddress) -> "UserEmailAddressNode":
        return cls(
            id=entity.id,
            address=entity.address,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            validated_at=entity.validated_at,
            last_validation_request_at=entity.last_validation_request_at,
        )


@strawberry.type
@register_node()
class UserNode(EntityNode[UserService], relay.Node):
    id: relay.NodeID[str]
    email_address: UserEmailAddressNode
    status: UserStatusNode
    language: LanguageNode
    private_data: Optional["UserPrivateDataNode"]
    created_at: datetime
    updated_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: User):
        return cls(
            id=entity.id,
            email_address=UserEmailAddressNode.from_obj(entity.email_address),
            status=UserStatusNode.from_obj(entity.status),
            language=LanguageNode.from_obj(entity.language),
            private_data=UserPrivateDataNode.from_obj(entity.private_data) if entity.private_data else None,
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
class PasswordResetRequestNode(ServiceNode[UserService]):
    success: bool


@strawberry.type
@register_node()
class ResetPasswordNode(ServiceNode[UserService]):
    success: bool


@strawberry.type
@register_node()
class VerifyEmailNode(ServiceNode[UserService]):
    success: bool


@strawberry.type
@register_node()
class AnonymizeUserNode(ServiceNode[UserService]):
    success: bool


@strawberry.type
@register_node()
class UserAuditLogNode(EntityNode[UserAuditLogService], relay.Node):
    """
    User audit log node for tracking user-related actions and observations.

    Accessible by super users and users with USER_ADMIN role.
    Provides audit trail for status changes, anonymization, and manual observations.
    """
    id: relay.NodeID[str]
    target_user: UserNode
    author_user: UserNode
    log_type: UserAuditLogTypeNode
    message: str
    created_at: datetime
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]

    @classmethod
    def from_obj(cls, entity: UserAuditLog) -> "UserAuditLogNode":
        return cls(
            id=entity.id,
            target_user=UserNode.from_obj(entity.target_user),
            author_user=UserNode.from_obj(entity.author_user),
            log_type=UserAuditLogTypeNode.from_obj(entity.log_type),
            message=entity.message,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        """
        Define allowed order by keys for UserAuditLog queries.

        Allowed sorting fields:
        - created_at: Log creation date (default)
        - log_type: Type of log entry
        """
        entity_class = self.service_class.entity_class

        return {
            "created_at": entity_class.created_at,
            "log_type": entity_class.log_type_id,
        }


@strawberry.type
@register_node()
class CreateUserObservationNode(ServiceNode[UserAuditLogService]):
    """Result node for creating user observation."""
    audit_log: UserAuditLogNode


@strawberry.type
@register_node()
class DeleteUserObservationNode(EntityNode[UserAuditLogService]):
    """Result node for deleting user observation."""
    success: bool

    @classmethod
    def from_obj(cls, entity: UserAuditLog) -> "DeleteUserObservationNode":
        return cls(success=True)

