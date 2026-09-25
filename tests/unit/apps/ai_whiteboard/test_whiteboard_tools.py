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


@pytest.fixture
def whiteboard_service():
    service = MagicMock()
    service.resolve_for_conversation = AsyncMock(return_value=BOARD)
    service.apply_operations = AsyncMock()
    service.describe = MagicMock(return_value=[{"name": "a"}])
    return service


@pytest.fixture
def service(whiteboard_service):
    app_manager = MagicMock()
    app_manager.get_service.return_value = whiteboard_service
    with patch.object(AIConversationService, "app_manager", app_manager, create=True), \
            patch.object(AIConversationService, "get_by_id", AsyncMock(return_value=SimpleNamespace(id="conv-1"))):
        yield AIConversationService


def context(**overrides):
    return {"session": MagicMock(), "conversation_id": "conv-1", **overrides}


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

        operations = whiteboard_service.apply_operations.await_args.args[1]
        assert operations == {"add": [{"name": "a"}]}
        assert result == {"whiteboard_id": "board-1", "title": "Board", "elements": [{"name": "a"}]}

    @pytest.mark.asyncio
    async def test_empty_patch_is_reported_not_applied(self, service, whiteboard_service):
        result = await service._handle_draw_on_whiteboard({"add": []}, context())
        assert result["error"] == "EMPTY_PATCH"
        whiteboard_service.apply_operations.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_none_arguments_are_an_empty_patch(self, service):
        result = await service._handle_draw_on_whiteboard(None, context())
        assert result["error"] == "EMPTY_PATCH"

    @pytest.mark.asyncio
    async def test_a_refused_patch_goes_back_to_the_model(self, service, whiteboard_service):
        whiteboard_service.apply_operations.side_effect = LysError(
            WHITEBOARD_UNKNOWN_ELEMENT, "arrow endpoint 'x' is not on the board"
        )

        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}]}, context())

        assert result == {"error": "WHITEBOARD_UNKNOWN_ELEMENT", "message": "arrow endpoint 'x' is not on the board"}

    @pytest.mark.asyncio
    async def test_an_unreachable_named_board_goes_back_to_the_model(self, service, whiteboard_service):
        whiteboard_service.resolve_for_conversation.side_effect = LysError(WHITEBOARD_NOT_FOUND, "no such board")

        result = await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "whiteboard_id": "x"}, context())

        assert result["error"] == "WHITEBOARD_NOT_FOUND"
        whiteboard_service.apply_operations.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_named_board_is_forwarded(self, service, whiteboard_service):
        await service._handle_draw_on_whiteboard({"add": [{"name": "a"}], "whiteboard_id": "wanted"}, context())
        assert whiteboard_service.resolve_for_conversation.await_args.kwargs["whiteboard_id"] == "wanted"

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
        whiteboard_service.resolve_for_conversation.side_effect = LysError(WHITEBOARD_NOT_FOUND, "no such board")
        result = await service._handle_read_whiteboard({"whiteboard_id": "x"}, context())
        assert result["error"] == "WHITEBOARD_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_no_conversation_is_reported(self, service):
        result = await service._handle_read_whiteboard(None, {})
        assert result["error"] == "NO_WHITEBOARD"
