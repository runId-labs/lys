"""AI modules."""

from . import core
from . import conversation
from . import webservice


__submodules__ = [
    core,           # AIService
    conversation,   # AIConversation, AIMessage, AIMessageFeedback
    webservice,     # Webservice with ai_tool field
]