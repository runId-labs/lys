"""
AIConversationService extension: the whiteboard tools, and the flags in step.

Registers ``draw_on_whiteboard`` and ``read_whiteboard`` on the executor the chatbot
builds for a turn, backs them with handlers that resolve the board themselves, and
keeps the conversation's visibility flags in step with the board it points at (see
the overrides below) - the conversation and its board are archived, restored, pinned
and unpinned together.

The handlers are stateless: they read ``conversation_id`` and ``session`` from the
execution context rather than being bound to a conversation when they are registered.
The factory below runs once per turn but is not handed the conversation, and a handler
closed over one could not be registered here at all.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from lys.apps.ai.modules.conversation.services import AIConversationService as BaseAIConversationService
from lys.apps.ai_whiteboard.modules.conversation import drafting
from lys.apps.ai_whiteboard.modules.conversation.tools import (
    DRAFT_ON_WHITEBOARD_TOOL,
    DRAW_ON_WHITEBOARD_TOOL,
    READ_WHITEBOARD_TOOL,
)
from lys.apps.ai_whiteboard.modules.whiteboard import scene as scene_tools
from lys.apps.ai_whiteboard.modules.whiteboard.consts import WHITEBOARD_NODE_NAME
from lys.core.errors import LysError
from lys.core.graphql.client import build_global_id, decode_global_id
from lys.core.registries import register_service

logger = logging.getLogger(__name__)

#: Returned to the model rather than raised: a tool that cannot find its board must
#: not end the turn, and the model can carry on answering without one.
NO_WHITEBOARD = "NO_WHITEBOARD"

#: The model named a board with something that is not a whiteboard GlobalID.
INVALID_WHITEBOARD_ID = "INVALID_WHITEBOARD_ID"

#: The model asked to edit a board and to copy one in the same call.
CONFLICTING_WHITEBOARDS = "CONFLICTING_WHITEBOARDS"

#: A drafted drawing the drafter could not lay out: nothing was written.
DRAFT_FAILED = "DRAFT_FAILED"


def _no_whiteboard(message: str) -> Dict[str, str]:
    """A tool result saying there is no board, in the shape the executor expects."""
    return {"error": NO_WHITEBOARD, "message": message}


def _named_board(
    arguments: Dict[str, Any], key: str = "whiteboard_id",
) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """
    The raw id of the board the model named under ``key``, or the error to hand back.

    The tools speak GlobalIDs, like every id crossing a tool boundary: the page context
    names the board on screen that way, and a tool result hands one back. The service
    behind works on raw ids, so the boundary decodes here - and refuses a raw uuid or
    another type's id rather than guessing, which would make a wrong id read as "no
    such board" instead of telling the model what to pass.

    Returns:
        (raw id, None) when a whiteboard GlobalID was named, (None, None) when none
        was, (None, error result) when the value is not a whiteboard GlobalID.
    """
    value = arguments.get(key)
    if value in (None, ""):
        return None, None

    decoded = decode_global_id(value)
    prefix = f"{WHITEBOARD_NODE_NAME}:"
    if decoded is None or not decoded.startswith(prefix):
        return None, {
            "error": INVALID_WHITEBOARD_ID,
            "message": (
                f"'{key}' must be a whiteboard id exactly as a whiteboard tool result "
                "or the page context gave it (an opaque base64 id). A raw uuid or an altered "
                "id is not accepted."
            ),
        }

    return decoded[len(prefix):], None


def _boards_of(
    arguments: Dict[str, Any],
) -> Tuple[Tuple[Optional[str], Optional[str]], Optional[Dict[str, str]]]:
    """
    The boards a draw call names - the one to change in place, the one to copy - as raw ids,
    or the error to hand back: an id that is not a whiteboard GlobalID, or both at once.
    """
    named_whiteboard_id, refused = _named_board(arguments)
    if refused:
        return (None, None), refused
    copy_from_whiteboard_id, refused = _named_board(arguments, "copy_from")
    if refused:
        return (None, None), refused
    if named_whiteboard_id and copy_from_whiteboard_id:
        return (None, None), {
            "error": CONFLICTING_WHITEBOARDS,
            "message": (
                "Give whiteboard_id to change that board, or copy_from to start a new board "
                "as its copy - not both"
            ),
        }
    return (named_whiteboard_id, copy_from_whiteboard_id), None


def _for_model(board: Dict[str, Any], conversation_board_id: Optional[str]) -> Dict[str, Any]:
    """
    A tool result as the model reads it: the board id as the GlobalID it passes back, and
    whether this board is the conversation's own.

    ``conversation_board`` is what lets the model tell "your board" from "the board the
    user has on screen": edited by id, a board stays where it belongs (see the draw
    handler), so "now do the same on yours" has to know which one is meant.
    """
    raw_id = str(board["whiteboard_id"])
    return {
        **board,
        "whiteboard_id": build_global_id(WHITEBOARD_NODE_NAME, raw_id),
        "conversation_board": raw_id == str(conversation_board_id),
    }


def _board_title(arguments: Dict[str, Any]) -> Optional[str]:
    """
    The name the model gave a board it opens, or None.

    The model names what it creates, at the moment it creates it: it knows the subject
    then, whereas the conversation title is written in the background and may not exist
    yet on the turn that opens the board. Anything but a non-blank string reads as no
    name, so the board falls back to the conversation title. Whitespace is collapsed: a
    name is shown on one line, in a header and a list.
    """
    title = arguments.get("title")
    if not isinstance(title, str):
        return None

    return " ".join(title.split()) or None


@register_service()
class AIConversationService(BaseAIConversationService):
    """
    Adds the whiteboard tools to every turn, and the flag sync to every action.

    Not gated on the page: a board is where a structured answer goes, and the model has
    to be able to open one wherever the question was asked. The flag overrides are not
    gated either: a conversation and the board it points at are one artifact in two
    listings, and no action on either may leave them apart.
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

        # Drafted once the consumer configured a drafter (drafting.py): the chatbot says what to draw,
        # the drafter lays it out. Otherwise the chatbot draws itself. One tool name either way, the
        # definition and its handler chosen together.
        if cls._drafts():
            executor.register_special_tool("draw_on_whiteboard", cls._handle_draft_on_whiteboard)
            tools.append(DRAFT_ON_WHITEBOARD_TOOL)
        else:
            executor.register_special_tool("draw_on_whiteboard", cls._handle_draw_on_whiteboard)
            tools.append(DRAW_ON_WHITEBOARD_TOOL)
        executor.register_special_tool("read_whiteboard", cls._handle_read_whiteboard)
        tools.append(READ_WHITEBOARD_TOOL)

        return executor

    @classmethod
    def _drafts(cls) -> bool:
        """Whether drawings are drafted: the consumer configured the drafter's endpoint."""
        return drafting.DRAFTING_PURPOSE in cls.app_manager.get_service("ai").get_config().endpoints

    # ==================== Visibility flags ====================

    @classmethod
    async def archive(cls, conversation: Any, session: Any) -> Any:
        """
        Archive a conversation, and the board it points at.

        The board is the artifact of the exchange that produced it, and the two stay in
        step: a flag acted on from either side lands on both. The base class owns the
        conversation's own flag (its rule, its idempotence); this override only carries
        the state over to the board, and the whiteboard service owns what happens there.

        Args:
            conversation: The conversation being archived
            session: The session of the request

        Returns:
            The archived conversation
        """
        archived = await super().archive(conversation, session)
        await cls.app_manager.get_service("whiteboard").follow_conversation_archive(conversation, session)
        return archived

    @classmethod
    async def unarchive(cls, conversation: Any, session: Any) -> Any:
        """
        Restore an archived conversation; the board it points at follows.

        Args:
            conversation: The conversation being restored
            session: The session of the request

        Returns:
            The restored conversation
        """
        restored = await super().unarchive(conversation, session)
        await cls.app_manager.get_service("whiteboard").follow_conversation_archive(conversation, session)
        return restored

    @classmethod
    async def pin(cls, conversation: Any, session: Any) -> Any:
        """
        Pin a conversation, and the board it points at.

        Same rule as :meth:`archive`, for the pin: orthogonal to the archive flag on
        both sides.

        Args:
            conversation: The conversation being pinned
            session: The session of the request

        Returns:
            The pinned conversation
        """
        pinned = await super().pin(conversation, session)
        await cls.app_manager.get_service("whiteboard").follow_conversation_pin(conversation, session)
        return pinned

    @classmethod
    async def unpin(cls, conversation: Any, session: Any) -> Any:
        """
        Unpin a conversation; the board it points at follows.

        Args:
            conversation: The conversation being unpinned
            session: The session of the request

        Returns:
            The unpinned conversation
        """
        unpinned = await super().unpin(conversation, session)
        await cls.app_manager.get_service("whiteboard").follow_conversation_pin(conversation, session)
        return unpinned

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
            for key in ("add", "update", "delete", "theme")
            if arguments.get(key)
        }
        boards, refused = _boards_of(arguments)
        if refused:
            return refused
        if not operations and not arguments.get("focus") and not boards[1]:
            return {
                "error": "EMPTY_PATCH",
                "message": "Nothing to do: give add, update or delete to draw, focus to show, or copy_from to copy",
            }
        return await cls._write_drawing(conversation, arguments, context, [operations] if operations else [], boards)

    @classmethod
    async def _handle_draft_on_whiteboard(
        cls, arguments: Dict[str, Any], context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Have a request drawn by the drafter (``drafting.py``), or bring elements of a board into view.

        The drafter lays out the request on the board it targets - the conversation's, one named
        by id, or the copy one opens -, read here as it stands; its patches are then written like
        any drawing. What the chatbot reads back is what this call drew, never the whole board:
        laying it out is no longer its job. A drafter that fails, or draws nothing, writes nothing
        and says so.
        """
        arguments = arguments or {}
        conversation = await cls._turn_conversation(context)
        if conversation is None:
            return _no_whiteboard("No whiteboard could be opened for this conversation")

        boards, refused = _boards_of(arguments)
        if refused:
            return refused
        request = arguments.get("request")
        request = request.strip() if isinstance(request, str) else ""
        if not request:
            if not arguments.get("focus") and not boards[1]:
                return {
                    "error": "EMPTY_PATCH",
                    "message": "Nothing to do: give request to draw, focus to show, or copy_from to copy",
                }
            return await cls._write_drawing(conversation, arguments, context, [], boards)
        if len(request) > drafting.REQUEST_MAX_LENGTH:
            return {
                "error": "REQUEST_TOO_LONG",
                "message": f"Describe the drawing in at most {drafting.REQUEST_MAX_LENGTH} characters",
            }
        links = drafting.asked_links(arguments.get("links"))
        if links is None:
            return {
                "error": "INVALID_LINKS",
                "message": (
                    f"'links' is a list of at most {drafting.MAX_LINKS} {{from, to}} pairs, each end the text "
                    f"of a box in at most {drafting.LINK_END_MAX_LENGTH} characters"
                ),
            }

        scene = await cls._scene_to_draft_on(conversation, boards, context["session"])
        if isinstance(scene, dict) and "error" in scene:
            return scene
        try:
            style = cls.app_manager.get_service("whiteboard").style()
        except LysError as e:
            # A palette or corners setting the board refuses: the chatbot's to say, not a failed turn
            return {"error": e.detail, "message": e.debug_message}
        draft = await drafting.draft(
            cls.app_manager.get_service("ai"), request, scene, cache_key=f"whiteboard-{conversation.id}",
            links=links, style=style,
        )
        await cls.app_manager.get_service("ai_agent_run").record(
            drafting.DRAFTING_PURPOSE, conversation.user_id, conversation.client_id, request,
            draft.calls, transcript=draft.messages, error=draft.error, provider=draft.provider,
            output=None if draft.error else {"drawn": draft.drawn, "note": draft.note, "issues": draft.issues},
        )
        if draft.error:
            logger.error(f"Whiteboard drafting failed for conversation '{conversation.id}': {draft.error}")
            return {"error": DRAFT_FAILED, "message": "The drawing could not be laid out; nothing was drawn."}
        if not draft.patches:
            return {"error": DRAFT_FAILED, "message": draft.note or "The drafter drew nothing; nothing was drawn."}

        # The view goes to what the drafter drew: the chatbot cannot know the names it chose, and a focus
        # naming one it did not would refuse the whole drawing
        drawing = {key: value for key, value in arguments.items() if key != "focus"}
        written = await cls._write_drawing(conversation, drawing, context, draft.patches, boards)
        if "error" in written:
            return written
        drawn = set(draft.drawn)
        written["drawn"] = [
            {key: element[key] for key in ("name", "kind", "text", "frame") if key in element}
            for element in written.pop("elements") if element["name"] in drawn
        ]
        if draft.note:
            written["note"] = draft.note
        if draft.issues:
            written["issues"] = draft.issues
        return written

    @classmethod
    async def _scene_to_draft_on(cls, conversation: Any, boards: Tuple[Optional[str], Optional[str]], session):
        """
        The scene the drafter lays out on: the board the call will write to, as it stands now -
        the copy's source for a copy, an empty scene for a board not opened yet.

        Read-only, in the turn's session: opening a board here would leave a second one behind
        when the write opens its own (see ``_handle_read_whiteboard``).
        """
        named_whiteboard_id, copy_from_whiteboard_id = boards
        whiteboard_service = cls.app_manager.get_service("whiteboard")
        try:
            if copy_from_whiteboard_id:
                whiteboard = await whiteboard_service.get_for_user(
                    copy_from_whiteboard_id, conversation.user_id, session,
                )
                if whiteboard is None:
                    return _no_whiteboard("The board to copy is not one of the user's")
            else:
                whiteboard = await whiteboard_service.find_for_conversation(
                    conversation.user_id, conversation.whiteboard_id, named_whiteboard_id, session,
                )
        except LysError as e:
            return {"error": e.detail, "message": e.debug_message}
        return (whiteboard.scene_json if whiteboard is not None else None) or scene_tools.empty_scene()

    @classmethod
    async def _write_drawing(
        cls,
        conversation: Any,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
        patches: List[Dict[str, Any]],
        boards: Tuple[Optional[str], Optional[str]],
    ) -> Dict[str, Any]:
        """
        Write patches on the board a call targets - or only bring ``focus`` into view - and keep
        the conversation's pointer on the board it opened.
        """
        named_whiteboard_id, copy_from_whiteboard_id = boards
        whiteboard_service = cls.app_manager.get_service("whiteboard")
        try:
            # Committed apart where the backend allows, so the board reaches the browser
            # now rather than at the end of the turn: the answer naming it is still being
            # written, and its first sentence is already being spoken.
            drawn = await whiteboard_service.draw(
                user_id=conversation.user_id,
                title=_board_title(arguments) or conversation.title,
                current_whiteboard_id=conversation.whiteboard_id,
                named_whiteboard_id=named_whiteboard_id,
                operations={},
                caller_session=context["session"],
                focus=arguments.get("focus") or None,
                copy_from_whiteboard_id=copy_from_whiteboard_id,
                patches=patches,
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
        #
        # Never to a board named by id: that one is the user's, edited where it is - the
        # board on screen, a template from last month. Taking it over would make it this
        # conversation's board too, so "now do the same on yours" would land on it, and
        # its flags would follow this conversation's. A board this turn opened - drawn
        # from nothing, or copied - is the conversation's own.
        if named_whiteboard_id is None and conversation.whiteboard_id != drawn["whiteboard_id"]:
            conversation.whiteboard_id = drawn["whiteboard_id"]
            context["session"].add(conversation)
            await context["session"].flush()

            # Born of this conversation, it takes its flags at birth (see
            # WhiteboardService.open_for_conversation for why an inherited state, not an
            # empty one).
            await whiteboard_service.follow_conversation_archive(conversation, context["session"])
            await whiteboard_service.follow_conversation_pin(conversation, context["session"])

        return _for_model(drawn, conversation.whiteboard_id)

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

        named_whiteboard_id, refused = _named_board(arguments)
        if refused:
            return refused

        whiteboard_service = cls.app_manager.get_service("whiteboard")
        try:
            whiteboard = await whiteboard_service.find_for_conversation(
                conversation.user_id,
                conversation.whiteboard_id,
                named_whiteboard_id,
                context["session"],
            )
        except LysError as e:
            return {"error": e.detail, "message": e.debug_message}
        if whiteboard is None:
            return _no_whiteboard("This conversation has no whiteboard yet: drawing on one opens it")

        return {
            "whiteboard_id": build_global_id(WHITEBOARD_NODE_NAME, str(whiteboard.id)),
            "conversation_board": str(whiteboard.id) == str(conversation.whiteboard_id),
            "title": whiteboard.title,
            "elements": whiteboard_service.describe(whiteboard),
            "slides": whiteboard_service.slides(whiteboard),
            "theme": whiteboard_service.theme(whiteboard),
        }
