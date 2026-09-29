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
from lys.core.errors import LysError
from lys.apps.ai_whiteboard.errors import WHITEBOARD_NOT_FOUND, WHITEBOARD_UNKNOWN_ELEMENT

BOARD = SimpleNamespace(id="board-1", title="Board")
DRAWN = {"whiteboard_id": "board-1", "title": "Board", "elements": [{"name": "a"}]}


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
    service.describe = MagicMock(return_value=[{"name": "a"}])
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

    def test_draw_declares_the_three_operations(self):
        properties = DRAW_ON_WHITEBOARD_TOOL["function"]["parameters"]["properties"]
        assert {"add", "update", "delete", "whiteboard_id"} <= set(properties)


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
        assert result == DRAWN

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

        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "whiteboard_id": "x"}, context())

        assert result["error"] == "WHITEBOARD_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_the_named_board_is_forwarded(self, service, whiteboard_service):
        await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "whiteboard_id": "wanted"}, context())
        kwargs = whiteboard_service.draw.await_args.kwargs
        assert kwargs["named_whiteboard_id"] == "wanted"

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
        assert result == {"whiteboard_id": "board-1", "title": "Board", "elements": [{"name": "a"}]}

    @pytest.mark.asyncio
    async def test_unreachable_board_goes_back_to_the_model(self, service, whiteboard_service):
        whiteboard_service.find_for_conversation.side_effect = LysError(WHITEBOARD_NOT_FOUND, "no such board")
        result = await service._handle_read_whiteboard({"whiteboard_id": "x"}, context())
        assert result["error"] == "WHITEBOARD_NOT_FOUND"

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
