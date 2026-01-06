"""
AI Conversation inputs.

GraphQL input types for AI conversation mutations.
"""

from typing import Optional, List

import strawberry
from strawberry.scalars import JSON

from lys.apps.ai.modules.conversation.models import AIMessageInputModel, AIToolResultModel


@strawberry.experimental.pydantic.input(model=AIMessageInputModel, all_fields=True)
class AIMessageInput:
    """Input for sending a message to the AI assistant."""
    pass


@strawberry.experimental.pydantic.type(model=AIToolResultModel, all_fields=True)
class AIToolResult:
    """Result of a tool execution."""
    pass


@strawberry.type
class FrontendAction:
    """Action to be executed by the frontend."""
    type: str  # "navigate", "refresh", etc.
    path: Optional[str] = None
    params: Optional[JSON] = None
    nodes: Optional[List[str]] = None  # Node types to refresh (e.g., ["ClientNode"])