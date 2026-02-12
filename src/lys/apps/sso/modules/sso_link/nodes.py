import strawberry
from datetime import datetime
from typing import List, Optional

from strawberry import relay

from lys.apps.sso.modules.sso_link.entities import UserSSOLink
from lys.apps.sso.modules.sso_link.services import UserSSOLinkService
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node


@register_node()
class UserSSOLinkNode(EntityNode[UserSSOLinkService], relay.Node):
    """GraphQL node for UserSSOLink entity."""
    id: relay.NodeID[str]
    provider: str
    external_email: str
    linked_at: datetime
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[UserSSOLink]

    @strawberry.field
    def user_id(self) -> relay.GlobalID:
        return relay.GlobalID("UserNode", self._entity.user_id)


@strawberry.type
class SSOProviderNode:
    """Represents a configured SSO provider available for authentication."""
    provider_id: str
    name: str
    login_url: str


@register_node()
class SSOProvidersNode(ServiceNode[UserSSOLinkService]):
    """Wrapper node containing the list of configured SSO providers."""
    providers: List[SSOProviderNode]


@register_node()
class UserSSOLinksNode(ServiceNode[UserSSOLinkService]):
    """Wrapper node containing the list of SSO links for a user."""
    links: List[UserSSOLinkNode]


@register_node()
class SSOSessionNode(ServiceNode[UserSSOLinkService]):
    """Represents SSO session data for pre-filling signup forms."""
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    provider: str = ""