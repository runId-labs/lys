"""
AI Conversation inputs.

GraphQL input types for AI conversation mutations.
"""

from typing import Optional, List

import strawberry
from strawberry.scalars import JSON

from lys.apps.ai.modules.conversation.models import (
    AIMessageInputModel,
    AIToolResultModel,
    PageContextModel,
)


@strawberry.experimental.pydantic.input(model=PageContextModel)
class PageContextInput:
    """
    Input for page context.

    Sent with chatbot messages to enable context-aware tool filtering
    and secure mutations with page params.
    """
    page_name: strawberry.auto
    params: Optional[JSON] = None


@strawberry.experimental.pydantic.input(model=AIMessageInputModel)
class AIMessageInput:
    """Input for sending a message to the AI assistant."""
    message: strawberry.auto
    conversation_id: strawberry.auto
    context: Optional[PageContextInput] = None


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
    continue_action: Optional[bool] = None  # If true, frontend should send "Continue" after navigate