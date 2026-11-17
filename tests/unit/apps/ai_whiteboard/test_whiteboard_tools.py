"""
Unit tests for the whiteboard chatbot tools: definitions and handlers.

The board and the service are stubbed. What is checked is the contract with the model:
what comes back when the call is wrong, and that nothing wrong ever escapes as an
exception through the turn.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lys.apps.ai_whiteboard.modules.conversation.services import AIConversationService
from lys.apps.ai_whiteboard.modules.conversation.tools import DRAW_ON_WHITEBOARD_TOOL, READ_WHITEBOARD_TOOL
from lys.apps.ai_whiteboard.modules.whiteboard.consts import ADD_ITEM_FIELDS, UPDATE_ITEM_FIELDS
from lys.core.errors import LysError
from lys.core.graphql.client import build_global_id
from lys.apps.ai_whiteboard.errors import WHITEBOARD_NOT_FOUND, WHITEBOARD_UNKNOWN_ELEMENT

BOARD = SimpleNamespace(id="board-1", title="Board")
DRAWN = {"whiteboard_id": "board-1", "title": "Board", "elements": [{"name": "a"}]}
# The tools speak GlobalIDs to the model; the service behind them keeps raw ids.
BOARD_GID = build_global_id("WhiteboardNode", "board-1")
NAMED_GID = build_global_id("WhiteboardNode", "board-9")
DRAWN_FOR_MODEL = {**DRAWN, "whiteboard_id": BOARD_GID, "conversation_board": True}


@pytest.fixture
def whiteboard_service():
    service = MagicMock()
    # The drawing commits apart, so the handler asks for the whole thing at once and
    # never holds a board across a session.
    service.draw = AsyncMock(return_value=DRAWN)
    service.find_for_conversation = AsyncMock(return_value=BOARD)
    service.apply_operations = AsyncMock()
    service.open_for_conversation = AsyncMock(return_value=BOARD)
    service.resolve_for_conversation = AsyncMock(return_value=BOARD)
    # Flag sync, reached when the turn opened the board (it was born here, not named).
    service.follow_conversation_archive = AsyncMock()
    service.follow_conversation_pin = AsyncMock()
    service.describe = MagicMock(return_value=[{"name": "a"}])
    service.slides = MagicMock(return_value=[{"index": 1}])
    service.theme = MagicMock(return_value={"background": "#ffffff", "stroke": "clean"})
    return service


@pytest.fixture
def conversation():
    """The turn's conversation: it owns the pointer, not the board."""
    return SimpleNamespace(id="conv-1", user_id="user-1", title="Titre", whiteboard_id=None)


@pytest.fixture
def service(whiteboard_service, conversation):
    app_manager = MagicMock()
    app_manager.get_service.return_value = whiteboard_service
    with patch.object(AIConversationService, "app_manager", app_manager, create=True), \
            patch.object(AIConversationService, "get_by_id", AsyncMock(return_value=conversation)):
        yield AIConversationService


def context(**overrides):
    # The turn's session: only the pointer is written through it, so flush is the
    # one call that has to be awaitable.
    session = MagicMock()
    session.flush = AsyncMock()
    return {"session": session, "conversation_id": "conv-1", **overrides}


class TestDefinitions:
    @pytest.mark.parametrize("tool,name", [
        (DRAW_ON_WHITEBOARD_TOOL, "draw_on_whiteboard"),
        (READ_WHITEBOARD_TOOL, "read_whiteboard"),
    ])
    def test_shape_and_name(self, tool, name):
        assert tool["type"] == "function"
        assert tool["function"]["name"] == name
        assert tool["function"]["parameters"]["type"] == "object"

    @pytest.mark.parametrize("operation,fields", [("add", ADD_ITEM_FIELDS), ("update", UPDATE_ITEM_FIELDS)])
    def test_the_fields_the_schema_declares_are_the_fields_the_scene_accepts(self, operation, fields):
        # The scene refuses any field outside its list, and the model only ever sends
        # what the schema declares: the two must name the same fields, or a declared
        # field would be refused - or an undeclared one accepted and ignored.
        declared = DRAW_ON_WHITEBOARD_TOOL["function"]["parameters"]["properties"][operation]["items"]["properties"]
        # The scene tolerates a repeated "kind" on an update that the schema does not declare.
        assert set(declared) <= set(fields)
        assert set(fields) - set(declared) <= {"kind"}

    def test_draw_declares_the_three_operations(self):
        properties = DRAW_ON_WHITEBOARD_TOOL["function"]["parameters"]["properties"]
        assert {"add", "update", "delete", "focus", "whiteboard_id", "title"} <= set(properties)


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_registers_both_handlers_and_definitions(self):
        executor = MagicMock()
        tools = []
        with patch(
            "lys.apps.ai.modules.conversation.services.AIConversationService._get_tool_executor",
            AsyncMock(return_value=executor),
        ):
            result = await AIConversationService._get_tool_executor(tools, MagicMock())

        assert result is executor
        registered = {call.args[0] for call in executor.register_special_tool.call_args_list}
        assert registered == {"draw_on_whiteboard", "read_whiteboard"}
        assert [t["function"]["name"] for t in tools] == ["draw_on_whiteboard", "read_whiteboard"]


class TestDrawHandler:
    @pytest.mark.asyncio
    async def test_applies_the_patch_and_returns_the_board(self, service, whiteboard_service):
        arguments = {"add": [{"name": "a"}], "update": [], "unknown": 1}

        result = await service._handle_draw_on_whiteboard(arguments, context())

        kwargs = whiteboard_service.draw.await_args.kwargs
        assert kwargs["operations"] == {"add": [{"name": "a"}]}
        assert result == DRAWN_FOR_MODEL

    @pytest.mark.asyncio
    async def test_a_board_opened_here_takes_the_name_the_model_gave_it(self, service, whiteboard_service):
        """The model names the board it opens: no dependency on the background conversation title."""
        await service._handle_draw_on_whiteboard(
            {"add": [{"name": "a"}], "title": "  Charges de\npersonnel   2025 "}, context(),
        )

        assert whiteboard_service.draw.await_args.kwargs["title"] == "Charges de personnel 2025"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("title", [None, "", "   ", 42])
    async def test_without_a_usable_name_the_board_falls_back_to_the_conversation_title(
        self, service, whiteboard_service, title,
    ):
        arguments = {"add": [{"name": "a"}]}
        if title is not None:
            arguments["title"] = title

        await service._handle_draw_on_whiteboard(arguments, context())

        assert whiteboard_service.draw.await_args.kwargs["title"] == "Titre"

    @pytest.mark.asyncio
    async def test_the_pointer_is_written_in_the_turns_transaction(
        self, service, whiteboard_service, conversation,
    ):
        """The board commits on its own; the pointer to it belongs to the turn."""
        ctx = context()

        await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, ctx)

        assert conversation.whiteboard_id == "board-1"
        ctx["session"].add.assert_called_once_with(conversation)

    @pytest.mark.asyncio
    async def test_a_pointer_already_there_is_not_rewritten(
        self, service, whiteboard_service, conversation,
    ):
        """Drawing twice in a turn must not rewrite the same value."""
        conversation.whiteboard_id = "board-1"
        ctx = context()

        await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, ctx)

        ctx["session"].add.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_board_opened_by_the_turn_inherits_the_conversations_flags(
        self, service, whiteboard_service, conversation,
    ):
        """The board was born here: its flags start where the conversation's stand."""
        ctx = context()

        await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, ctx)

        whiteboard_service.follow_conversation_archive.assert_awaited_once_with(conversation, ctx["session"])
        whiteboard_service.follow_conversation_pin.assert_awaited_once_with(conversation, ctx["session"])

    @pytest.mark.asyncio
    async def test_a_named_board_is_edited_in_place_never_taken_over(
        self, service, whiteboard_service, conversation,
    ):
        """The board on screen stays the user's: no pointer, no flag sync, and the model is told."""
        whiteboard_service.draw.return_value = {**DRAWN, "whiteboard_id": "board-9"}
        ctx = context()

        result = await service._handle_draw_on_whiteboard(
            {"add": [{"name": "a"}], "whiteboard_id": NAMED_GID}, ctx,
        )

        assert conversation.whiteboard_id is None
        ctx["session"].add.assert_not_called()
        whiteboard_service.follow_conversation_archive.assert_not_awaited()
        whiteboard_service.follow_conversation_pin.assert_not_awaited()
        assert result["whiteboard_id"] == NAMED_GID
        assert result["conversation_board"] is False

    @pytest.mark.asyncio
    async def test_a_copy_becomes_the_conversations_board(
        self, service, whiteboard_service, conversation,
    ):
        """Copied from a model, the new board is born here: pointer and flags follow."""
        whiteboard_service.draw.return_value = {**DRAWN, "whiteboard_id": "copy-1"}
        ctx = context()

        result = await service._handle_draw_on_whiteboard({"copy_from": NAMED_GID, "title": "CODIR 2027"}, ctx)

        kwargs = whiteboard_service.draw.await_args.kwargs
        assert kwargs["copy_from_whiteboard_id"] == "board-9"
        assert kwargs["named_whiteboard_id"] is None
        assert kwargs["title"] == "CODIR 2027"
        assert conversation.whiteboard_id == "copy-1"
        whiteboard_service.follow_conversation_archive.assert_awaited_once_with(conversation, ctx["session"])
        assert result["conversation_board"] is True

    @pytest.mark.asyncio
    async def test_editing_a_board_and_copying_one_at_once_is_refused(self, service, whiteboard_service):
        result = await service._handle_draw_on_whiteboard(
            {"add": [{"name": "a"}], "whiteboard_id": BOARD_GID, "copy_from": NAMED_GID}, context(),
        )

        assert result["error"] == "CONFLICTING_WHITEBOARDS"
        whiteboard_service.draw.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_copy_from_that_is_not_a_whiteboard_global_id_is_refused(self, service, whiteboard_service):
        result = await service._handle_draw_on_whiteboard({"copy_from": "board-9"}, context())

        assert result["error"] == "INVALID_WHITEBOARD_ID"
        whiteboard_service.draw.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_focus_alone_is_a_call_worth_making(self, service, whiteboard_service):
        """'Show me the org chart': nothing to draw, something to bring into view."""
        result = await service._handle_draw_on_whiteboard({"focus": ["organigramme"]}, context())

        kwargs = whiteboard_service.draw.await_args.kwargs
        assert kwargs["operations"] == {}
        assert kwargs["focus"] == ["organigramme"]
        assert result == DRAWN_FOR_MODEL

    @pytest.mark.asyncio
    async def test_a_patch_without_focus_passes_none(self, service, whiteboard_service):
        await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "focus": []}, context())
        assert whiteboard_service.draw.await_args.kwargs["focus"] is None

    @pytest.mark.asyncio
    async def test_empty_patch_is_reported_not_applied(self, service, whiteboard_service):
        result = await service._handle_draw_on_whiteboard({"add": []}, context())
        assert result["error"] == "EMPTY_PATCH"
        whiteboard_service.draw.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_none_arguments_are_an_empty_patch(self, service):
        result = await service._handle_draw_on_whiteboard(None, context())
        assert result["error"] == "EMPTY_PATCH"

    @pytest.mark.asyncio
    async def test_a_refused_patch_goes_back_to_the_model(self, service, whiteboard_service):
        whiteboard_service.draw.side_effect = LysError(
            WHITEBOARD_UNKNOWN_ELEMENT, "arrow endpoint 'x' is not on the board"
        )

        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, context())

        assert result == {"error": "WHITEBOARD_UNKNOWN_ELEMENT", "message": "arrow endpoint 'x' is not on the board"}

    @pytest.mark.asyncio
    async def test_an_unreachable_named_board_goes_back_to_the_model(self, service, whiteboard_service):
        whiteboard_service.draw.side_effect = LysError(
            WHITEBOARD_NOT_FOUND, "no such board"
        )

        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "whiteboard_id": NAMED_GID}, context())

        assert result["error"] == "WHITEBOARD_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_the_named_board_is_forwarded(self, service, whiteboard_service):
        await service._handle_draw_on_whiteboard(
            {"add": [{"name": "a"}], "whiteboard_id": build_global_id("WhiteboardNode", "wanted")}, context(),
        )
        kwargs = whiteboard_service.draw.await_args.kwargs
        assert kwargs["named_whiteboard_id"] == "wanted"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("named", [
        "board-9",
        "9b7f6c1e-2f4a-4c1d-9a51-6c0f2a1e3b44",
        build_global_id("CompanyNode", "board-9"),
    ])
    async def test_an_id_that_is_not_a_whiteboard_global_id_is_refused(self, service, whiteboard_service, named):
        """A raw uuid or another type's id is not guessed at: the model is told what to pass."""
        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "whiteboard_id": named}, context())

        assert result["error"] == "INVALID_WHITEBOARD_ID"
        whiteboard_service.draw.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ctx", [{}, {"session": MagicMock()}, {"conversation_id": "conv-1"}])
    async def test_no_conversation_or_session_is_reported(self, service, ctx):
        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, ctx)
        assert result["error"] == "NO_WHITEBOARD"

    @pytest.mark.asyncio
    async def test_a_vanished_conversation_is_reported(self, service):
        with patch.object(AIConversationService, "get_by_id", AsyncMock(return_value=None)):
            result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, context())
        assert result["error"] == "NO_WHITEBOARD"


class TestReadHandler:
    @pytest.mark.asyncio
    async def test_reads_the_board_back(self, service):
        result = await service._handle_read_whiteboard({}, context())
        assert result == {
            "whiteboard_id": BOARD_GID, "conversation_board": False,
            "title": "Board", "elements": [{"name": "a"}], "slides": [{"index": 1}],
            "theme": {"background": "#ffffff", "stroke": "clean"},
        }

    @pytest.mark.asyncio
    async def test_unreachable_board_goes_back_to_the_model(self, service, whiteboard_service):
        whiteboard_service.find_for_conversation.side_effect = LysError(WHITEBOARD_NOT_FOUND, "no such board")
        result = await service._handle_read_whiteboard({"whiteboard_id": NAMED_GID}, context())
        assert result["error"] == "WHITEBOARD_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_the_board_on_screen_is_read_by_its_global_id(self, service, whiteboard_service, conversation):
        """The page context names the board on screen as a GlobalID: the read reaches it."""
        await service._handle_read_whiteboard({"whiteboard_id": NAMED_GID}, context())

        assert whiteboard_service.find_for_conversation.await_args.args[2] == "board-9"

    @pytest.mark.asyncio
    async def test_a_raw_uuid_is_refused(self, service, whiteboard_service):
        result = await service._handle_read_whiteboard(
            {"whiteboard_id": "9b7f6c1e-2f4a-4c1d-9a51-6c0f2a1e3b44"}, context(),
        )

        assert result["error"] == "INVALID_WHITEBOARD_ID"
        whiteboard_service.find_for_conversation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reading_never_opens_a_board(self, service, whiteboard_service):
        """Nothing to read is an answer, not a reason to create — see the handler."""
        whiteboard_service.find_for_conversation.return_value = None

        result = await service._handle_read_whiteboard({}, context())

        assert result["error"] == "NO_WHITEBOARD"
        whiteboard_service.open_for_conversation.assert_not_awaited()
        whiteboard_service.resolve_for_conversation.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_conversation_is_reported(self, service):
        result = await service._handle_read_whiteboard(None, {})
        assert result["error"] == "NO_WHITEBOARD"
