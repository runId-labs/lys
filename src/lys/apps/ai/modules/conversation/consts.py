"""
AI Conversation constants.
"""

from enum import Enum


# Purpose for conversation-based AI interactions
AI_PURPOSE_CHATBOT = "chatbot"


class AIMessageRole(str, Enum):
    """Role of a message in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AIFeedbackRating(str, Enum):
    """Rating for feedback on a message."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"