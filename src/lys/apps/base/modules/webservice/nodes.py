from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.util import classproperty
from strawberry import relay

from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class WebserviceNode(EntityNode[WebserviceService], relay.Node):
    id: relay.NodeID[str]
    code: str
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "code": self.entity_class.id,
            "created_at": self.entity_class.created_at
        }