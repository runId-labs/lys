from typing import Optional, List

import strawberry
from pydantic import BaseModel


class AIMessageInputModel(BaseModel):
    """Pydantic model for AI message input validation."""
    message: str
    conversation_id: Optional[str] = None


@strawberry.experimental.pydantic.input(model=AIMessageInputModel, all_fields=True)
class AIMessageInput:
    """Input for sending a message to the AI assistant."""
    pass


class AIToolResultModel(BaseModel):
    """Model for tool execution result."""
    tool_name: str
    result: str
    success: bool


@strawberry.experimental.pydantic.type(model=AIToolResultModel, all_fields=True)
class AIToolResult:
    """Result of a tool execution."""
    pass
