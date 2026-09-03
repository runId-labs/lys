"""
AI Conversation nodes.

GraphQL node types for AI conversation responses.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List

import strawberry
from sqlalchemy.util import classproperty
from strawberry import relay

from lys.apps.ai.modules.conversation.consts import DISPLAY_TITLE_MAX_LENGTH
from lys.apps.ai.modules.conversation.entities import AIConversation, AIMessage
from lys.apps.ai.modules.conversation.inputs import AIToolResult, FrontendAction
from lys.apps.ai.modules.conversation.services import AIConversationService, AIMessageService
from lys.core.contexts import Info
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node


@register_node()
class AIConversationNode(EntityNode[AIConversationService], relay.Node):
    """A conversation session between a user and the AI."""
    id: relay.NodeID[str]
    purpose: str
    title: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    archived_at: Optional[datetime]
    _entity: strawberry.Private[AIConversation]

    @strawberry.field(description="Owner of the conversation.")
    def user_id(self) -> relay.GlobalID:
        return relay.GlobalID("UserNode", self._entity.user_id)

    @strawberry.field(
        description="Title to show in a listing: the conversation title, falling back to the "
                    "truncated opening message while no title has been set."
    )
    async def display_title(self, info: Info) -> Optional[str]:
        """
        Resolve the title a listing can display.

        A titled conversation costs nothing extra: the fallback query only runs while
        `title` is null, which a conversation leaves as soon as it is titled.
        """
        if self._entity.title:
            return self._entity.title

        service = info.context.app_manager.get_service("ai_conversation")
        content = await service.get_opening_message_content(self._entity.id, info.context.session)

        return content[:DISPLAY_TITLE_MAX_LENGTH] if content else None

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "created_at": self.entity_class.created_at,
            "updated_at": self.entity_class.updated_at,
        }


@register_node()
class AIConversationMessageNode(EntityNode[AIMessageService], relay.Node):
    """A stored message of a conversation, as replayed in the chat history.

    Distinct from AIMessageNode, which is the payload returned when sending a
    message and carries no persisted identity.
    """
    id: relay.NodeID[str]
    role: str
    content: Optional[str]
    created_at: datetime
    _entity: strawberry.Private[AIMessage]

    @strawberry.field(description="Conversation this message belongs to.")
    def conversation_id(self) -> relay.GlobalID:
        return relay.GlobalID("AIConversationNode", self._entity.conversation_id)

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        return {
            "created_at": self.entity_class.created_at,
        }


@register_node()
class AIMessageNode(ServiceNode[AIConversationService]):
    """Response from AI assistant."""
    content: str
    conversation_id: Optional[str] = None
    tool_calls_count: int = 0
    tool_results: Optional[List[AIToolResult]] = None
    frontend_actions: Optional[List[FrontendAction]] = None

    message: str = "AI response generated successfully"