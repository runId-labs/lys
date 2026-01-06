"""
AI Conversation nodes.

GraphQL node types for AI conversation responses.
"""

from typing import Optional, List, TYPE_CHECKING

from lys.apps.ai.modules.conversation.inputs import AIToolResult, FrontendAction
from lys.core.graphql.nodes import ServiceNode
from lys.core.registries import register_node

if TYPE_CHECKING:
    from lys.apps.ai.modules.conversation.services import AIConversationService


@register_node()
class AIMessageNode(ServiceNode["AIConversationService"]):
    """Response from AI assistant."""
    content: str
    conversation_id: Optional[str] = None
    tool_calls_count: int = 0
    tool_results: Optional[List[AIToolResult]] = None
    frontend_actions: Optional[List[FrontendAction]] = None

    message: str = "AI response generated successfully"