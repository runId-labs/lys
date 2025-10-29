from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.base.modules.log.entities import Log
from lys.apps.base.modules.log.services import LogService
from lys.core.graphql.nodes import EntityNode
from lys.core.registers import register_node


@strawberry.type
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

    @classmethod
    def from_obj(cls, entity: Log) -> "LogNode":
        return cls(
            id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            message=entity.message,
            file_name=entity.file_name,
            line=entity.line,
            traceback=entity.traceback,
            context=entity.context,
        )
