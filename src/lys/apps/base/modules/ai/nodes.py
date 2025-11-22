from typing import Optional, List

from lys.apps.base.modules.ai.inputs import AIToolResult
from lys.apps.base.modules.ai.services import AIService
from lys.core.graphql.nodes import ServiceNode
from lys.core.registers import register_node


@register_node()
class AIMessageNode(ServiceNode[AIService]):
    """Response from AI assistant."""
    content: str
    conversation_id: Optional[str] = None
    tool_calls_count: int = 0
    tool_results: Optional[List[AIToolResult]] = None

    message: str = "AI response generated successfully"
