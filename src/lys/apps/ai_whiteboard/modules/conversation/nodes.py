"""
AIConversation node extension: the board the conversation writes to.

The pointer lives on the conversation - a conversation has at most one board of its own -
so it is read where it lives rather than through a lookup of its own. A client listing
conversations gets the answer in the same row, at no extra cost.
"""

from typing import Optional

import strawberry
from strawberry import relay

from lys.apps.ai.modules.conversation.nodes import AIConversationNode as BaseAIConversationNode
from lys.apps.ai_whiteboard.modules.conversation.entities import AIConversation
from lys.apps.ai_whiteboard.modules.whiteboard.consts import WHITEBOARD_NODE_NAME
from lys.core.registries import register_node


@register_node()
class AIConversationNode(BaseAIConversationNode):
    """A conversation, plus the whiteboard it has opened for itself."""

    _entity: strawberry.Private[AIConversation]

    @strawberry.field(
        description="The whiteboard this conversation writes to, or null while it has "
                    "opened none. A conversation opens at most one board of its own, and "
                    "the chatbot fills that one unless it is told otherwise."
    )
    def whiteboard_id(self) -> Optional[relay.GlobalID]:
        """
        Expose the pointer as a GlobalID.

        Clients only ever handle GlobalIDs - the update signal hands one out and the
        whiteboard query takes the same back - so the raw column is translated here
        rather than leaving each caller to guess which form it received.
        """
        if not self._entity.whiteboard_id:
            return None

        return relay.GlobalID(WHITEBOARD_NODE_NAME, self._entity.whiteboard_id)
