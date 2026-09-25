"""
Whiteboard nodes.

GraphQL types for the whiteboard: the scene as the editor consumes it, and the
revision it has to send back when it saves.
"""

from datetime import datetime
from typing import Any, Dict, Optional

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay
from strawberry.scalars import JSON

from lys.apps.ai_whiteboard.modules.whiteboard.entities import Whiteboard
from lys.apps.ai_whiteboard.modules.whiteboard.services import WhiteboardService
from lys.core.graphql.nodes import EntityNode
from lys.core.registries import register_node


@register_node()
class WhiteboardNode(EntityNode[WhiteboardService], relay.Node):
    """A whiteboard: its scene, and the revision that scene is at."""

    id: relay.NodeID[str]
    title: str
    created_at: datetime
    updated_at: Optional[datetime]
    _entity: strawberry.Private[Whiteboard]

    @strawberry.field(
        description="The Excalidraw scene: elements, appState, and the files map images "
                    "refer to by id. Handed to the editor as is."
    )
    def scene(self) -> JSON:
        return self._entity.scene_json or {}

    @strawberry.field(
        description="Revision of the scene. Send it back when saving: the server refuses a "
                    "save written from an older one rather than overwriting what it did not "
                    "know about, and a signal carrying a higher revision means an update was "
                    "missed and the board must be refetched."
    )
    def revision(self) -> int:
        return self._entity.revision

    @strawberry.field(description="Owner of the whiteboard.")
    def user_id(self) -> relay.GlobalID:
        return relay.GlobalID("UserNode", self._entity.user_id)

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "created_at": self.entity_class.created_at,
            "updated_at": self.entity_class.updated_at,
            "title": self.entity_class.title,
        }
