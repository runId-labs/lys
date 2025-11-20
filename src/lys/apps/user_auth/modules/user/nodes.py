from datetime import datetime
from typing import Optional, Dict, Any

import strawberry
from strawberry import relay
from strawberry.types import Info

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


@register_node()
class UserNode(EntityNode[UserService], relay.Node):
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
    async def private_data(self, info: Info) -> Optional["UserPrivateDataNode"]:
        """Get the user's private data (nullable)."""
        return await self._lazy_load_relation('private_data', UserPrivateDataNode, info)

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
    created_at: datetime
    updated_at: Optional[datetime]
    anonymized_at: Optional[datetime]
    _entity: strawberry.Private[UserPrivateData]

    @strawberry.field(description="User gender")
    async def gender(self, info: Info) -> Optional[GenderNode]:
        """Get the user's gender (nullable)."""
        return await self._lazy_load_relation('gender', GenderNode, info)


@register_node()
class UserOneTimeTokenNode(EntityNode[UserOneTimeTokenService], relay.Node):
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    used_at: Optional[datetime]
    status_id: str
    type_id: str
    _entity: strawberry.Private[UserOneTimeToken]

    @strawberry.field(description="User associated with this token")
    async def user(self, info: Info) -> UserNode:
        """Get the user associated with this one-time token."""
        return await self._lazy_load_relation('user', UserNode, info)


@register_node()
class PasswordResetRequestNode(ServiceNode[UserService]):
    success: bool


@register_node()
class ResetPasswordNode(ServiceNode[UserService]):
    success: bool


@register_node()
class VerifyEmailNode(ServiceNode[UserService]):
    success: bool


@register_node()
class AnonymizeUserNode(ServiceNode[UserService]):
    success: bool


@register_node()
class ConnectedUserSessionNode(ServiceNode[UserService]):
    """
    Connected user session information.

    Returns session metadata including token expiration and XSRF protection.
    """
    success: bool
    access_token_expire_in: int
    xsrf_token: str


@register_node()
class UserAuditLogNode(EntityNode[UserAuditLogService], relay.Node):
    """
    User audit log node for tracking user-related actions and observations.

    Accessible by super users and users with USER_ADMIN role.
    Provides audit trail for status changes, anonymization, and manual observations.
    """
    id: relay.NodeID[str]
    message: str
    created_at: datetime
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]
    _entity: strawberry.Private[UserAuditLog]

    @strawberry.field(description="User targeted by this audit log")
    async def target_user(self, info: Info) -> UserNode:
        """Get the user targeted by this audit log entry."""
        return await self._lazy_load_relation('target_user', UserNode, info)

    @strawberry.field(description="User who authored this audit log")
    async def author_user(self, info: Info) -> UserNode:
        """Get the user who created this audit log entry."""
        return await self._lazy_load_relation('author_user', UserNode, info)

    @strawberry.field(description="Type of audit log entry")
    async def log_type(self, info: Info) -> UserAuditLogTypeNode:
        """Get the type of this audit log entry."""
        return await self._lazy_load_relation('log_type', UserAuditLogTypeNode, info)

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


@register_node()
class CreateUserObservationNode(ServiceNode[UserAuditLogService]):
    """Result node for creating user observation."""
    audit_log: UserAuditLogNode


@register_node()
class DeleteUserObservationNode(EntityNode[UserAuditLogService]):
    """Result node for deleting user observation."""
    success: bool

    @classmethod
    def from_obj(cls, entity: UserAuditLog) -> "DeleteUserObservationNode":
        return cls(success=True)

