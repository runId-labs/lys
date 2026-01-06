"""
AI Conversation models.

Pydantic models for AI conversation data validation.
"""

from typing import Optional

from pydantic import BaseModel


class AIMessageInputModel(BaseModel):
    """Pydantic model for AI message input validation."""
    message: str
    conversation_id: Optional[str] = None


class AIToolResultModel(BaseModel):
    """Model for tool execution result."""
    tool_name: str
    result: str
    success: bool