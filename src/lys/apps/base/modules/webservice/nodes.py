from datetime import datetime
from typing import Optional, Dict, Any, List

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay
from strawberry.types import Info

from lys.apps.base.modules.access_level.nodes import AccessLevelNode
from lys.apps.base.modules.webservice.entities import Webservice
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node


@register_node()
class RegisterWebservicesNode(ServiceNode[WebserviceService]):
    """Response node for webservice registration from business microservices."""
    success: bool
    registered_count: int
    message: str = "Webservices registered successfully"


@register_node()
class WebserviceNode(EntityNode[WebserviceService], relay.Node):
    id: relay.NodeID[str]
    code: str
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool
    _entity: strawberry.Private[Webservice]

    @strawberry.field(description="Access levels associated with this webservice")
    async def access_levels(self, info: Info) -> List[AccessLevelNode]:
        """Get the access levels associated with this webservice."""
        return await self._lazy_load_relation_list("access_levels", AccessLevelNode, info)

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "code": self.entity_class.id,
            "created_at": self.entity_class.created_at
        }


@register_node()
class AccessedWebserviceNode(EntityNode[WebserviceService], relay.Node):
    id: relay.NodeID[str]
    code: str
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool
    _entity: strawberry.Private[Webservice]

    @strawberry.field(description="Access levels through which the current user can access this webservice")
    async def user_access_levels(self, info: Info) -> List[AccessLevelNode]:
        """Get the access levels the connected user qualifies for."""
        webservice_service = info.context.app_manager.get_service("webservice")
        session = info.context.session
        connected_user = info.context.connected_user

        access_levels = await webservice_service.get_user_access_levels(
            self._entity,
            connected_user,
            session
        )
        return [AccessLevelNode.from_obj(al) for al in access_levels]

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "code": self.entity_class.id,
            "created_at": self.entity_class.created_at
        }