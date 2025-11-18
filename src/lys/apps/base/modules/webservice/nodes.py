from datetime import datetime
from typing import Optional, Dict, Any

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay

from lys.apps.base.modules.webservice.entities import Webservice
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.graphql.nodes import EntityNode
from lys.core.registers import register_node


@register_node()
class WebserviceNode(EntityNode[WebserviceService], relay.Node):
    id: relay.NodeID[str]
    code: str
    enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool

    def __init__(
        self,
        id: str,
        code: str,
        enabled: bool,
        created_at: datetime,
        updated_at: Optional[datetime],
        is_public: bool,
    ):
        self.id = id
        self.code = code
        self.enabled = enabled

        self.created_at = created_at
        self.updated_at = updated_at
        self.is_public = is_public

    @classmethod
    def from_obj(cls, entity: Webservice):
        return cls(
            id=entity.id,
            code=entity.code,
            enabled=entity.enabled,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_public=entity.is_public
        )

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "code": self.entity_class.id,
            "created_at": self.entity_class.created_at
        }