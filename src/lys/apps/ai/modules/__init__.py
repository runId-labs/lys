"""AI modules."""

from . import core
from . import conversation
from . import text_improvement
from . import agent


__submodules__ = [
    core,              # AIService
    conversation,      # AIConversation, AIMessage, AIMessageFeedback
    text_improvement,  # TextImprovementService, improveText mutation
    agent,             # AIAgentRun, AIAgentService (agents as tools)
]