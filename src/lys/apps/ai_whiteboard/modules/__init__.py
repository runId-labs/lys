"""Whiteboard app modules."""

from . import whiteboard
from . import conversation


__submodules__ = [
    whiteboard,    # Whiteboard entity
    conversation,  # AIConversation extension (whiteboard_id)
]
