"""
AI Conversation models.

Pydantic models for AI conversation data validation.
"""

from typing import Optional, Dict, Any

from pydantic import BaseModel


class PageContextModel(BaseModel):
    """
    Pydantic model for page context.

    Used to send current page information with chatbot messages for:
    - Tool filtering by page (only expose tools relevant to the current page)
    - Secure mutations (inject page params like company_id, year)
    - Reduce hallucinations (chatbot knows what data user is viewing)
    """
    page_name: str
    params: Optional[Dict[str, Any]] = None


class AIMessageInputModel(BaseModel):
    """Pydantic model for AI message input validation."""
    message: str
    conversation_id: Optional[str] = None
    context: Optional[PageContextModel] = None


class AIToolResultModel(BaseModel):
    """Model for tool execution result."""
    tool_name: str
    result: str
    success: bool