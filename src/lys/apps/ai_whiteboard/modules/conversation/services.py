"""
AIConversationService extension: the whiteboard tools.

Registers ``draw_on_whiteboard`` and ``read_whiteboard`` on the executor the chatbot
builds for a turn, and backs them with handlers that resolve the board themselves.

The handlers are stateless: they read ``conversation_id`` and ``session`` from the
execution context rather than being bound to a conversation when they are registered.
The factory below runs once per turn but is not handed the conversation, and a handler
closed over one could not be registered here at all.
"""

import logging
from typing import Any, Dict, List

from lys.apps.ai.modules.conversation.services import AIConversationService as BaseAIConversationService
from lys.apps.ai_whiteboard.modules.conversation.tools import (
    DRAW_ON_WHITEBOARD_TOOL,
    READ_WHITEBOARD_TOOL,
)
from lys.core.errors import LysError
from lys.core.registries import register_service

logger = logging.getLogger(__name__)

#: Returned to the model rather than raised: a tool that cannot find its board must
#: not end the turn, and the model can carry on answering without one.
NO_WHITEBOARD = "NO_WHITEBOARD"


def _no_whiteboard(message: str) -> Dict[str, str]:
    """A tool result saying there is no board, in the shape the executor expects."""
    return {"error": NO_WHITEBOARD, "message": message}


@register_service()
class AIConversationService(BaseAIConversationService):
    """
    Adds the whiteboard tools to every turn.

    Not gated on the page: a board is where a structured answer goes, and the model has
    to be able to open one wherever the question was asked.
    """

    @classmethod
    async def _get_tool_executor(
        cls,
        tools: List[Dict[str, Any]],
        info: Any,
        accessible_routes: List[Dict[str, Any]] = None,
        page_context=None,
    ):
        executor = await super()._get_tool_executor(tools, info, accessible_routes, page_context)

        executor.register_special_tool("draw_on_whiteboard", cls._handle_draw_on_whiteboard)
        executor.register_special_tool("read_whiteboard", cls._handle_read_whiteboard)
        tools.append(DRAW_ON_WHITEBOARD_TOOL)
        tools.append(READ_WHITEBOARD_TOOL)

        return executor

    # ==================== Tool handlers ====================

    @classmethod
    async def _turn_conversation(cls, context: Dict[str, Any]):
        """
        The conversation a tool call belongs to, from the execution context alone.

        None when the turn carries no conversation — which should not happen, and must
        not raise through the turn if it somehow does.
        """
        session = context.get("session")
        conversation_id = context.get("conversation_id")
        if not session or not conversation_id:
            return None

        return await cls.get_by_id(conversation_id, session)

    @classmethod
    async def _handle_draw_on_whiteboard(
        cls, arguments: Dict[str, Any], context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply a patch to a board, or bring elements of it into the user's view.

        Returns the board as it stands afterwards, so the model can see the result of its
        own call without spending a second one reading it back.

        A refused patch comes back as an error the model can act on — a name it invented,
        an arrow to nothing — rather than an exception ending the turn. It is the caller
        that can fix it, and only if it is told.
        """
        arguments = arguments or {}
        conversation = await cls._turn_conversation(context)
        if conversation is None:
            return _no_whiteboard("No whiteboard could be opened for this conversation")

        operations = {
            key: arguments[key]
            for key in ("add", "update", "delete")
            if arguments.get(key)
        }
        focus = arguments.get("focus") or None
        if not operations and not focus:
            return {
                "error": "EMPTY_PATCH",
                "message": "Nothing to do: give add, update or delete to draw, or focus to show",
            }

        whiteboard_service = cls.app_manager.get_service("whiteboard")
        try:
            # Committed apart where the backend allows, so the board reaches the browser
            # now rather than at the end of the turn: the answer naming it is still being
            # written, and its first sentence is already being spoken.
            drawn = await whiteboard_service.draw(
                user_id=conversation.user_id,
                title=conversation.title,
                current_whiteboard_id=conversation.whiteboard_id,
                named_whiteboard_id=arguments.get("whiteboard_id"),
                operations=operations,
                caller_session=context["session"],
                focus=focus,
            )
        except LysError as e:
            logger.info(f"Whiteboard patch refused for conversation '{conversation.id}': {e.debug_message}")
            # debug_message, not str(e): the latter is the bare code, which tells the model
            # nothing it can act on. Every error reaching here is one the whiteboard raises
            # itself, and their text names only what the caller supplied - "arrow endpoint
            # 'x' is not on the board" - so nothing internal travels back with it.
            return {"error": e.detail, "message": e.debug_message}

        # The pointer, in the turn's own transaction: the board belongs to the user, the
        # pointer to the conversation. Written only when it moves — a board drawn twice
        # in a turn must not rewrite the same value.
        if conversation.whiteboard_id != drawn["whiteboard_id"]:
            conversation.whiteboard_id = drawn["whiteboard_id"]
            context["session"].add(conversation)
            await context["session"].flush()

        return drawn

    @classmethod
    async def _handle_read_whiteboard(
        cls, arguments: Dict[str, Any], context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Read a board back: names, kinds, texts and links, never positions.

        Reading never opens a board, and that is not a detail. A board opened here would
        live in the turn's transaction, uncommitted and therefore invisible to the
        drawing that follows — which draws in a transaction of its own and would open a
        SECOND board, leaving the first behind, empty, already announced to the browser.
        Nothing to read is an answer the model can act on: it draws, and drawing opens
        the board.
        """
        arguments = arguments or {}
        conversation = await cls._turn_conversation(context)
        if conversation is None:
            return _no_whiteboard("No whiteboard could be opened for this conversation")

        whiteboard_service = cls.app_manager.get_service("whiteboard")
        try:
            whiteboard = await whiteboard_service.find_for_conversation(
                conversation.user_id,
                conversation.whiteboard_id,
                arguments.get("whiteboard_id"),
                context["session"],
            )
        except LysError as e:
            return {"error": e.detail, "message": e.debug_message}
        if whiteboard is None:
            return _no_whiteboard("This conversation has no whiteboard yet: drawing on one opens it")

        return {
            "whiteboard_id": whiteboard.id,
            "title": whiteboard.title,
            "elements": whiteboard_service.describe(whiteboard),
        }
