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
    async def _resolve_board(cls, arguments: Dict[str, Any], context: Dict[str, Any]):
        """
        Find the board a tool call is about, from the execution context alone.

        Returns ``(whiteboard, session)``, or ``(None, session)`` when the turn carries no
        conversation — which should not happen, and must not raise through the turn if it
        somehow does. A board the model named and cannot reach raises ``LysError``, which
        the handlers hand back to it.
        """
        session = context.get("session")
        conversation_id = context.get("conversation_id")
        if not session or not conversation_id:
            return None, session

        conversation = await cls.get_by_id(conversation_id, session)
        if conversation is None:
            return None, session

        whiteboard_service = cls.app_manager.get_service("whiteboard")
        whiteboard = await whiteboard_service.resolve_for_conversation(
            conversation, session, whiteboard_id=arguments.get("whiteboard_id"),
        )
        return whiteboard, session

    @classmethod
    async def _handle_draw_on_whiteboard(
        cls, arguments: Dict[str, Any], context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply a patch to a board.

        Returns the board as it stands afterwards, so the model can see the result of its
        own call without spending a second one reading it back.

        A refused patch comes back as an error the model can act on — a name it invented,
        an arrow to nothing — rather than an exception ending the turn. It is the caller
        that can fix it, and only if it is told.
        """
        arguments = arguments or {}
        try:
            whiteboard, session = await cls._resolve_board(arguments, context)
        except LysError as e:
            return {"error": e.detail, "message": e.debug_message}
        if whiteboard is None:
            return {"error": "NO_WHITEBOARD", "message": "No whiteboard could be opened for this conversation"}

        operations = {
            key: arguments[key]
            for key in ("add", "update", "delete")
            if arguments.get(key)
        }
        if not operations:
            return {"error": "EMPTY_PATCH", "message": "Nothing to draw: add, update or delete is required"}

        whiteboard_service = cls.app_manager.get_service("whiteboard")
        try:
            await whiteboard_service.apply_operations(whiteboard, operations, session)
        except LysError as e:
            logger.info(f"Whiteboard patch refused on '{whiteboard.id}': {e.debug_message}")
            # debug_message, not str(e): the latter is the bare code, which tells the model
            # nothing it can act on. Every error reaching here is one the whiteboard raises
            # itself, and their text names only what the caller supplied - "arrow endpoint
            # 'x' is not on the board" - so nothing internal travels back with it.
            return {"error": e.detail, "message": e.debug_message}

        return {
            "whiteboard_id": whiteboard.id,
            "title": whiteboard.title,
            "elements": whiteboard_service.describe(whiteboard),
        }

    @classmethod
    async def _handle_read_whiteboard(
        cls, arguments: Dict[str, Any], context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Read a board back: names, kinds, texts and links, never positions."""
        arguments = arguments or {}
        try:
            whiteboard, _ = await cls._resolve_board(arguments, context)
        except LysError as e:
            return {"error": e.detail, "message": e.debug_message}
        if whiteboard is None:
            return {"error": "NO_WHITEBOARD", "message": "No whiteboard could be opened for this conversation"}

        whiteboard_service = cls.app_manager.get_service("whiteboard")

        return {
            "whiteboard_id": whiteboard.id,
            "title": whiteboard.title,
            "elements": whiteboard_service.describe(whiteboard),
        }
