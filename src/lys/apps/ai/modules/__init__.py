"""AI modules."""

from . import core
from . import conversation
from . import text_improvement


__submodules__ = [
    core,              # AIService
    conversation,      # AIConversation, AIMessage, AIMessageFeedback
    text_improvement,  # TextImprovementService, improveText mutation
]