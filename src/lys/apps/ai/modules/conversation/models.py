"""
AI Conversation models.

Pydantic models for AI conversation data validation.
"""

from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from lys.apps.ai.modules.conversation.consts import DISPLAY_TITLE_MAX_LENGTH
from lys.core.graphql.client import extract_id_from_global_id


def extract_conversation_id(value: str) -> str:
    """
    Turn the conversation GlobalID a client holds into the raw entity id.

    Clients only ever see GlobalIDs - the chat stream hands one out and the
    conversation listing returns the same - so both entry points into a conversation
    (the GraphQL mutation and the SSE endpoint) decode here rather than each rolling
    its own. Raises ValueError on anything that is not a GlobalID carrying a UUID, so
    a malformed reference is refused instead of silently opening a new conversation.
    """
    try:
        node_id = extract_id_from_global_id(value)
    except Exception:
        raise ValueError("Invalid conversation ID format")

    try:
        UUID(node_id)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Invalid conversation ID format")

    return node_id


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

    @field_validator("conversation_id", mode="before")
    @classmethod
    def validate_conversation_id(cls, value: Optional[str]) -> Optional[str]:
        """Accept the GlobalID the client holds and store the raw id."""
        if value is None:
            return None

        return extract_conversation_id(value)


class AIToolResultModel(BaseModel):
    """Model for tool execution result."""
    tool_name: str
    result: str
    success: bool


class UpdateAIConversationTitleInputModel(BaseModel):
    """Input model for renaming a conversation."""
    title: str = Field(
        ...,
        min_length=1,
        max_length=DISPLAY_TITLE_MAX_LENGTH,
        description="New title of the conversation",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Reject a blank title: it would silently read as the generated fallback."""
        title = value.strip()
        if not title:
            raise ValueError("Title cannot be empty")

        return title
