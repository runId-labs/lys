"""
AI Conversation models.

Pydantic models for AI conversation data validation.
"""

import json
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from lys.apps.ai.modules.conversation.consts import DISPLAY_TITLE_MAX_LENGTH, MAX_TOOL_ANSWER_LENGTH
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
    - Secure mutations (page params are injected as tool-argument defaults)
    - Reduce hallucinations (chatbot knows what data user is viewing)

    The envelope is the framework's and is validated as such; ``params`` is free-form and
    its keys belong to the consumer. Nothing here reads them by name - the only generic
    rule applied to them is the ``*_id`` suffix handling in the tool executors.
    """
    page_name: str
    params: Optional[Dict[str, Any]] = None


class AIToolAnswerModel(BaseModel):
    """
    The user's answer to an open tool call (see AIConversationService.user_answered_tools).

    Written by the client, read by the model as that call's result: the id must name a call
    the server left open — checked by the service, not here — and the result is bounded.
    """
    tool_call_id: str = Field(..., min_length=1, max_length=100)
    result: Dict[str, Any]

    @field_validator("result")
    @classmethod
    def validate_result(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        """Refuse an answer the model would read as a wall of text."""
        if len(json.dumps(value, ensure_ascii=False)) > MAX_TOOL_ANSWER_LENGTH:
            raise ValueError(f"Tool answer exceeds {MAX_TOOL_ANSWER_LENGTH} characters")

        return value


class AIMessageInputModel(BaseModel):
    """
    Pydantic model for AI message input validation.

    A turn carries either ``message`` or ``tool_answers`` — the user's answers to the
    calls the last turn left open (see AIConversationService.user_answered_tools). The
    service refuses both or neither, for every entry point.

    ``client_generated`` marks a ``message`` the client application wrote on its own
    rather than the user (see AIMessage.is_client_generated); the service refuses it on
    ``tool_answers``, which write no message.
    """
    message: Optional[str] = None
    conversation_id: Optional[str] = None
    context: Optional[PageContextModel] = None
    tool_answers: Optional[List[AIToolAnswerModel]] = None
    client_generated: bool = False

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
