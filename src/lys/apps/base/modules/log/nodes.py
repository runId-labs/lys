from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.base.modules.log.services import LogService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class LogNode(EntityNode[LogService], relay.Node):
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    message: str
    file_name: str
    line: int
    traceback: str
    context: Optional[strawberry.scalars.JSON]
