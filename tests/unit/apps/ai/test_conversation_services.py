"""
Unit tests for AI Conversation services.

Tests AIConversationService, AIMessageService, and AIMessageFeedbackService
using mocks to avoid database dependencies.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from lys.apps.ai.modules.conversation.consts import (
    AIMessageRole,
    AIFeedbackRating,
    AI_PURPOSE_CHATBOT,
)


# Note: _build_messages tests are in integration tests because they require
# real SQLAlchemy entities for select() statements


class TestAIConversationServiceGetOrCreate:
    """Tests for get_or_create method."""

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app_manager."""
        return MagicMock()

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_or_create_with_existing_conversation(self, mock_app_manager, mock_session):
        """Test getting existing conversation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        existing_conv = MagicMock()
        existing_conv.user_id = "user-123"

        with patch.object(AIConversationService, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_conv

            result = await AIConversationService.get_or_create(
                user_id="user-123",
                session=mock_session,
                conversation_id="conv-123"
            )

        assert result == existing_conv
        mock_get.assert_called_once_with("conv-123", mock_session)

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_when_not_found(self, mock_app_manager, mock_session):
        """Test creating new conversation when not found."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        new_conv = MagicMock()

        with patch.object(AIConversationService, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with patch.object(AIConversationService, "create", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = new_conv

                result = await AIConversationService.get_or_create(
                    user_id="user-123",
                    session=mock_session,
                    conversation_id="nonexistent"
                )

        assert result == new_conv
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_without_conversation_id(self, mock_app_manager, mock_session):
        """Test creating new conversation when no ID provided."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        new_conv = MagicMock()

        with patch.object(AIConversationService, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = new_conv

            result = await AIConversationService.get_or_create(
                user_id="user-123",
                session=mock_session,
                conversation_id=None
            )

        assert result == new_conv
        mock_create.assert_called_once_with(
            mock_session,
            user_id="user-123",
            purpose=AI_PURPOSE_CHATBOT,
        )

    @pytest.mark.asyncio
    async def test_get_or_create_wrong_user_creates_new(self, mock_app_manager, mock_session):
        """Test that wrong user's conversation triggers new creation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        existing_conv = MagicMock()
        existing_conv.user_id = "other-user"  # Different user

        new_conv = MagicMock()

        with patch.object(AIConversationService, "get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = existing_conv

            with patch.object(AIConversationService, "create", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = new_conv

                result = await AIConversationService.get_or_create(
                    user_id="user-123",
                    session=mock_session,
                    conversation_id="conv-123"
                )

        assert result == new_conv


class TestAIConversationServiceArchive:
    """Tests for archive method."""

    @pytest.mark.asyncio
    async def test_archive_conversation(self):
        """Test archiving a conversation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_session = AsyncMock()
        updated_conv = MagicMock()

        with patch.object(AIConversationService, "update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = updated_conv

            result = await AIConversationService.archive("conv-123", mock_session)

        assert result is True
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "conv-123"
        assert call_args[0][1] == mock_session
        assert "archived_at" in call_args[1]

    @pytest.mark.asyncio
    async def test_archive_nonexistent_conversation(self):
        """Test archiving a nonexistent conversation returns False."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_session = AsyncMock()

        with patch.object(AIConversationService, "update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = None

            result = await AIConversationService.archive("nonexistent", mock_session)

        assert result is False


class TestAIMessageServiceAddToolResult:
    """Tests for AIMessageService.add_tool_result method."""

    @pytest.mark.asyncio
    async def test_add_tool_result(self):
        """Test adding a tool result message."""
        from lys.apps.ai.modules.conversation.services import AIMessageService

        mock_session = AsyncMock()
        mock_message = MagicMock()

        with patch.object(AIMessageService, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_message

            result = await AIMessageService.add_tool_result(
                conversation_id="conv-123",
                tool_call_id="call-456",
                result={"data": "test result"},
                session=mock_session
            )

        assert result == mock_message
        mock_create.assert_called_once_with(
            mock_session,
            conversation_id="conv-123",
            role=AIMessageRole.TOOL.value,
            tool_call_id="call-456",
            tool_result={"data": "test result"},
        )


class TestAIMessageFeedbackServiceRateMessage:
    """Tests for AIMessageFeedbackService.rate_message method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_rate_message_new_feedback(self, mock_session):
        """Test rating a message creates new feedback."""
        from lys.apps.ai.modules.conversation.services import AIMessageFeedbackService

        mock_feedback = MagicMock()

        with patch.object(
            AIMessageFeedbackService,
            "_get_or_create_feedback",
            new_callable=AsyncMock
        ) as mock_get_create:
            mock_get_create.return_value = mock_feedback

            result = await AIMessageFeedbackService.rate_message(
                message_id="msg-123",
                user_id="user-123",
                rating=AIFeedbackRating.THUMBS_UP,
                session=mock_session,
                comment="Great response!"
            )

        assert result == mock_feedback
        assert mock_feedback.rating == AIFeedbackRating.THUMBS_UP.value
        assert mock_feedback.comment == "Great response!"
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_message_without_comment(self, mock_session):
        """Test rating without comment doesn't override existing comment."""
        from lys.apps.ai.modules.conversation.services import AIMessageFeedbackService

        mock_feedback = MagicMock()
        mock_feedback.comment = "Existing comment"

        with patch.object(
            AIMessageFeedbackService,
            "_get_or_create_feedback",
            new_callable=AsyncMock
        ) as mock_get_create:
            mock_get_create.return_value = mock_feedback

            result = await AIMessageFeedbackService.rate_message(
                message_id="msg-123",
                user_id="user-123",
                rating=AIFeedbackRating.THUMBS_DOWN,
                session=mock_session,
                comment=None
            )

        assert mock_feedback.rating == AIFeedbackRating.THUMBS_DOWN.value
        # Comment should not be modified when None is passed
        assert mock_feedback.comment == "Existing comment"


class TestAIMessageFeedbackServiceAddComment:
    """Tests for AIMessageFeedbackService.add_comment method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_add_comment(self, mock_session):
        """Test adding a comment to feedback."""
        from lys.apps.ai.modules.conversation.services import AIMessageFeedbackService

        mock_feedback = MagicMock()

        with patch.object(
            AIMessageFeedbackService,
            "_get_or_create_feedback",
            new_callable=AsyncMock
        ) as mock_get_create:
            mock_get_create.return_value = mock_feedback

            result = await AIMessageFeedbackService.add_comment(
                message_id="msg-123",
                user_id="user-123",
                comment="This was helpful",
                session=mock_session
            )

        assert result == mock_feedback
        assert mock_feedback.comment == "This was helpful"
        mock_session.flush.assert_called_once()


class TestAIConversationServiceBuildSystemPrompt:
    """Tests for _build_system_prompt method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_build_system_prompt_returns_no_segments_without_inputs(self, mock_session):
        """Without page behaviour or context data, no segments are produced."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        result = await AIConversationService._build_system_prompt()

        assert result == []

    @pytest.mark.asyncio
    async def test_build_system_prompt_page_segment_is_cacheable(self, mock_session):
        """The page-specific prompt becomes a single cacheable segment."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        page_behaviour = {
            "prompt": "Focus on helping with customer support tasks."
        }

        result = await AIConversationService._build_system_prompt(
            page_behaviour=page_behaviour
        )

        assert result == [
            {"content": "Focus on helping with customer support tasks.", "cache": True}
        ]

    @pytest.mark.asyncio
    async def test_build_system_prompt_context_segment_is_volatile(self, mock_session):
        """Dynamic context becomes a single non-cacheable segment."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        context_data = {
            "Current Order": "Order #12345 - Status: Pending"
        }

        result = await AIConversationService._build_system_prompt(
            context_data=context_data
        )

        assert len(result) == 1
        segment = result[0]
        assert segment["cache"] is False
        assert "Dynamic context" in segment["content"]
        assert "Current Order" in segment["content"]
        assert "Order #12345" in segment["content"]

    @pytest.mark.asyncio
    async def test_build_system_prompt_orders_cacheable_before_volatile(self, mock_session):
        """The stable page segment precedes the volatile context segment."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        result = await AIConversationService._build_system_prompt(
            page_behaviour={"prompt": "Page prompt."},
            context_data={"Order": "Order #12345"},
        )

        assert [seg["cache"] for seg in result] == [True, False]
        assert result[0]["content"] == "Page prompt."
        assert "Order #12345" in result[1]["content"]

    @pytest.mark.asyncio
    async def test_build_system_prompt_stable_context_is_cacheable_first_segment(self, mock_session):
        """The stable context layer is cacheable and ordered before the page prompt."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        result = await AIConversationService._build_system_prompt(
            page_behaviour={"prompt": "Page prompt."},
            context_data={"Order": "Order #12345"},
            stable_context="Stable session map.",
        )

        # Layer A (stable) -> page (stable) -> dynamic context (volatile).
        assert result[0] == {"content": "Stable session map.", "cache": True}
        assert result[1] == {"content": "Page prompt.", "cache": True}
        assert result[2]["cache"] is False
        assert [seg["cache"] for seg in result] == [True, True, False]


class TestAIConversationServiceGetStableContext:
    """Tests for the _get_stable_context extension hook."""

    @pytest.mark.asyncio
    async def test_base_returns_none(self):
        """The base framework injects no stable context; consumers override this hook."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        result = await AIConversationService._get_stable_context(
            AsyncMock(), {"sub": "user-1"}, None, MagicMock()
        )
        assert result is None


# ========== Streaming Helpers ==========


class TestFormatSSE:
    """Tests for _format_sse helper."""

    def test_format_sse_basic(self):
        """Test SSE formatting with simple data."""
        from lys.apps.ai.modules.conversation.services import _format_sse

        result = _format_sse("token", {"content": "hello"})

        assert result.startswith("event: token\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        data = json.loads(result.split("data: ")[1].strip())
        assert data == {"content": "hello"}

    def test_format_sse_error_event(self):
        """Test SSE formatting for error events."""
        from lys.apps.ai.modules.conversation.services import _format_sse

        result = _format_sse("error", {"message": "Something failed", "code": "ERR"})

        assert "event: error\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data["message"] == "Something failed"
        assert data["code"] == "ERR"

    def test_format_sse_done_event(self):
        """Test SSE formatting for done events."""
        from lys.apps.ai.modules.conversation.services import _format_sse

        result = _format_sse("done", {"conversationId": "conv-1"})

        assert "event: done\n" in result
        data = json.loads(result.split("data: ")[1].strip())
        assert data["conversationId"] == "conv-1"


class TestAccumulateToolCalls:
    """Tests for _accumulate_tool_calls helper."""

    def test_accumulate_single_chunk(self):
        """Test accumulating a single complete tool call chunk."""
        from lys.apps.ai.modules.conversation.services import _accumulate_tool_calls

        acc = {}
        _accumulate_tool_calls(acc, [
            {"index": 0, "id": "call-1", "function": {"name": "get_users", "arguments": '{"limit": 10}'}}
        ])

        assert 0 in acc
        assert acc[0]["id"] == "call-1"
        assert acc[0]["function"]["name"] == "get_users"
        assert acc[0]["function"]["arguments"] == '{"limit": 10}'

    def test_accumulate_partial_arguments(self):
        """Test accumulating arguments across multiple chunks."""
        from lys.apps.ai.modules.conversation.services import _accumulate_tool_calls

        acc = {}
        _accumulate_tool_calls(acc, [
            {"index": 0, "id": "call-1", "function": {"name": "search", "arguments": '{"q": '}}
        ])
        _accumulate_tool_calls(acc, [
            {"index": 0, "function": {"arguments": '"hello"}'}}
        ])

        assert acc[0]["function"]["arguments"] == '{"q": "hello"}'
        assert acc[0]["id"] == "call-1"

    def test_accumulate_multiple_tools(self):
        """Test accumulating multiple parallel tool calls."""
        from lys.apps.ai.modules.conversation.services import _accumulate_tool_calls

        acc = {}
        _accumulate_tool_calls(acc, [
            {"index": 0, "id": "call-1", "function": {"name": "tool_a", "arguments": "{}"}},
            {"index": 1, "id": "call-2", "function": {"name": "tool_b", "arguments": "{}"}},
        ])

        assert len(acc) == 2
        assert acc[0]["function"]["name"] == "tool_a"
        assert acc[1]["function"]["name"] == "tool_b"

    def test_accumulate_default_index(self):
        """Test that missing index defaults to 0."""
        from lys.apps.ai.modules.conversation.services import _accumulate_tool_calls

        acc = {}
        _accumulate_tool_calls(acc, [
            {"id": "call-1", "function": {"name": "my_tool", "arguments": "{}"}}
        ])

        assert 0 in acc
        assert acc[0]["function"]["name"] == "my_tool"


class TestFinalizeToolCalls:
    """Tests for _finalize_tool_calls helper."""

    def test_finalize_empty_accumulator(self):
        """Test finalizing empty accumulator returns empty list."""
        from lys.apps.ai.modules.conversation.services import _finalize_tool_calls

        assert _finalize_tool_calls({}) == []

    def test_finalize_single_tool(self):
        """Test finalizing single tool call."""
        from lys.apps.ai.modules.conversation.services import _finalize_tool_calls

        acc = {
            0: {"id": "call-1", "type": "function", "function": {"name": "test", "arguments": "{}"}}
        }
        result = _finalize_tool_calls(acc)

        assert len(result) == 1
        assert result[0]["id"] == "call-1"

    def test_finalize_sorted_by_index(self):
        """Test that finalized list is sorted by index."""
        from lys.apps.ai.modules.conversation.services import _finalize_tool_calls

        acc = {
            2: {"id": "call-3", "type": "function", "function": {"name": "c", "arguments": "{}"}},
            0: {"id": "call-1", "type": "function", "function": {"name": "a", "arguments": "{}"}},
            1: {"id": "call-2", "type": "function", "function": {"name": "b", "arguments": "{}"}},
        }
        result = _finalize_tool_calls(acc)

        assert [r["id"] for r in result] == ["call-1", "call-2", "call-3"]


class TestStreamingShims:
    """Tests for _StreamingInfo and _StreamingContext shim classes."""

    def test_streaming_info_structure(self):
        """Test that _StreamingInfo provides expected interface."""
        from lys.apps.ai.modules.conversation.services import _StreamingInfo

        connected_user = {"sub": "user-123", "is_super_user": False}
        info = _StreamingInfo(connected_user=connected_user, access_token="tok-abc")

        assert info.context.connected_user == connected_user
        assert info.context.access_token == "tok-abc"
        assert info.context.frontend_actions == []

    def test_streaming_context_frontend_actions_mutable(self):
        """Test that frontend_actions list is mutable."""
        from lys.apps.ai.modules.conversation.services import _StreamingContext

        ctx = _StreamingContext(connected_user={}, access_token="tok")
        ctx.frontend_actions.append({"action": "navigate", "to": "/home"})

        assert len(ctx.frontend_actions) == 1


# ========== _prepare_chat_context ==========


class TestPrepareChatContext:
    """Tests for _prepare_chat_context shared setup method."""

    @pytest.fixture
    def connected_user(self):
        return {
            "sub": "user-123",
            "is_super_user": False,
            "webservices": {"ws_a": {}},
            "organizations": {},
        }

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_info(self, connected_user):
        info = MagicMock()
        info.context.connected_user = connected_user
        info.context.access_token = "tok-abc"
        info.context.frontend_actions = []
        return info

    @pytest.fixture
    def _setup_mocks(self):
        """Patch all external dependencies of _prepare_chat_context."""
        from lys.apps.ai.modules.conversation.services import AIConversationService
        from lys.apps.ai.modules.core.services import AIToolService

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-123"
        mock_message_service = AsyncMock()
        mock_ai_service = AsyncMock()

        mock_app_manager = MagicMock()
        mock_app_manager.settings.get_plugin_config.return_value = {"chatbot": {}}
        mock_app_manager.get_service.side_effect = lambda name: {
            "ai_message": mock_message_service,
            "ai": mock_ai_service,
        }.get(name, MagicMock())

        with patch.object(AIToolService, "get_accessible_tools", new_callable=AsyncMock) as mock_tools, \
             patch.object(AIConversationService, "_get_routes_manifest", return_value=None), \
             patch.object(AIConversationService, "_build_system_prompt", new_callable=AsyncMock,
                          return_value=[{"content": "sys prompt", "cache": True}]), \
             patch.object(AIConversationService, "_load_current_summary", new_callable=AsyncMock, return_value=None), \
             patch.object(AIConversationService, "_get_tool_executor", new_callable=AsyncMock) as mock_executor, \
             patch.object(AIConversationService, "get_or_create", new_callable=AsyncMock, return_value=mock_conversation), \
             patch.object(AIConversationService, "_build_messages", new_callable=AsyncMock, return_value=[]), \
             patch.object(AIConversationService, "app_manager", mock_app_manager):

            mock_tools.return_value = [
                {"webservice": "ws_a", "definition": {"type": "function", "function": {"name": "ws_a"}}, "operation_type": "query"},
            ]
            mock_executor.return_value = MagicMock()

            yield {
                "mock_tools": mock_tools,
                "mock_executor": mock_executor,
                "mock_conversation": mock_conversation,
                "mock_message_service": mock_message_service,
                "mock_ai_service": mock_ai_service,
            }

    @pytest.mark.asyncio
    async def test_returns_expected_keys(self, connected_user, mock_session, mock_info, _setup_mocks):
        """Test that _prepare_chat_context returns all expected keys."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        ctx = await AIConversationService._prepare_chat_context(
            user_id="user-123",
            content="Hello",
            session=mock_session,
            connected_user=connected_user,
            info=mock_info,
        )

        expected_keys = {"tools", "llm_tools", "executor", "conversation", "message_service", "ai_service", "messages", "info", "user_message_id"}
        assert set(ctx.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_messages_contain_system_and_user(self, connected_user, mock_session, mock_info, _setup_mocks):
        """Test that messages list includes system prompt and user message."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        ctx = await AIConversationService._prepare_chat_context(
            user_id="user-123",
            content="What can you do?",
            session=mock_session,
            connected_user=connected_user,
            info=mock_info,
        )

        messages = ctx["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "sys prompt"
        # The cache flag from the segment is carried onto the system message.
        assert messages[0]["cache"] is True
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What can you do?"

    @pytest.mark.asyncio
    async def test_saves_user_message_to_db(self, connected_user, mock_session, mock_info, _setup_mocks):
        """Test that user message is saved to DB during context preparation."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mocks = _setup_mocks
        await AIConversationService._prepare_chat_context(
            user_id="user-123",
            content="Test message",
            session=mock_session,
            connected_user=connected_user,
            info=mock_info,
        )

        mocks["mock_message_service"].create.assert_called_once_with(
            mock_session,
            conversation_id="conv-123",
            role=AIMessageRole.USER.value,
            content="Test message",
        )

    @pytest.mark.asyncio
    async def test_llm_tools_extracts_definitions(self, connected_user, mock_session, mock_info, _setup_mocks):
        """Test that llm_tools contains only the definition part of each tool."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        ctx = await AIConversationService._prepare_chat_context(
            user_id="user-123",
            content="Hello",
            session=mock_session,
            connected_user=connected_user,
            info=mock_info,
        )

        # Should have ws_a definition + CONFIRM_ACTION_TOOL
        llm_tools = ctx["llm_tools"]
        assert len(llm_tools) >= 1
        # First tool should be the extracted definition, not the full tool dict
        first_tool = llm_tools[0]
        assert "type" in first_tool
        assert "webservice" not in first_tool

    @pytest.mark.asyncio
    async def test_passes_info_through(self, connected_user, mock_session, mock_info, _setup_mocks):
        """Test that the provided info object is returned as-is."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        ctx = await AIConversationService._prepare_chat_context(
            user_id="user-123",
            content="Hello",
            session=mock_session,
            connected_user=connected_user,
            info=mock_info,
        )

        assert ctx["info"] is mock_info


# ========== chat_with_tools ==========


class TestChatWithTools:
    """Tests for chat_with_tools agent loop."""

    @pytest.fixture
    def connected_user(self):
        return {"sub": "user-123", "is_super_user": False, "webservices": {}, "organizations": {}}

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_info(self, connected_user):
        info = MagicMock()
        info.context.connected_user = connected_user
        info.context.access_token = "tok"
        info.context.frontend_actions = []
        return info

    def _make_ai_response(self, content="Response", tool_calls=None, provider="mistral", model="m"):
        from lys.apps.ai.utils.providers.abstracts import AIResponse
        return AIResponse(
            content=content,
            tool_calls=tool_calls,
            provider=provider,
            model=model,
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )

    @pytest.mark.asyncio
    async def test_simple_response_no_tools(self, mock_session, mock_info):
        """Test chat_with_tools returns response when LLM makes no tool calls."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        mock_ai_service = AsyncMock()
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=self._make_ai_response("Hello!"))

        ctx = {
            "executor": MagicMock(),
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Hi"}],
            "info": mock_info,
        }

        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            result = await AIConversationService.chat_with_tools(
                user_id="user-123", content="Hi", session=mock_session,
                info=mock_info,
            )

        assert result["content"] == "Hello!"
        assert result["conversation_id"] == "conv-1"
        assert result["tool_calls_count"] == 0

    @pytest.mark.asyncio
    async def test_tool_error_sanitized(self, mock_session, mock_info):
        """Test that tool execution errors are sanitized before sending to LLM."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        mock_ai_service = AsyncMock()
        mock_executor = AsyncMock()

        # First call: LLM requests a tool call
        tool_call_response = self._make_ai_response(
            content="",
            tool_calls=[{
                "id": "call-1",
                "function": {"name": "dangerous_tool", "arguments": "{}"},
            }],
        )
        # Second call: LLM gives final response after tool error
        final_response = self._make_ai_response("I encountered an issue.")

        mock_ai_service.chat_with_purpose = AsyncMock(
            side_effect=[tool_call_response, final_response]
        )

        # Tool execution raises an exception with sensitive info
        mock_executor.execute = AsyncMock(
            side_effect=Exception("Connection to internal-db:5432 refused (password=s3cr3t)")
        )

        ctx = {
            "executor": mock_executor,
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [{"type": "function", "function": {"name": "dangerous_tool"}}],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Do it"}],
            "info": mock_info,
        }

        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            result = await AIConversationService.chat_with_tools(
                user_id="user-123", content="Do it", session=mock_session,
                info=mock_info,
            )

        # Verify the error sent to LLM is sanitized (no internal details)
        tool_error_results = [r for r in result["tool_results"] if not r["success"]]
        assert len(tool_error_results) == 1
        assert "dangerous_tool" in tool_error_results[0]["result"]
        assert "failed to execute" in tool_error_results[0]["result"]
        # Must NOT contain the original sensitive error message
        assert "password" not in tool_error_results[0]["result"]
        assert "s3cr3t" not in tool_error_results[0]["result"]
        assert "5432" not in tool_error_results[0]["result"]

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self, mock_session, mock_info):
        """Test that max iterations returns appropriate message."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        mock_ai_service = AsyncMock()
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"data": "result"})

        # Always return tool calls to force max iterations
        tool_response = self._make_ai_response(
            content="",
            tool_calls=[{"id": "call-1", "function": {"name": "loop_tool", "arguments": "{}"}}],
        )
        mock_ai_service.chat_with_purpose = AsyncMock(return_value=tool_response)

        ctx = {
            "executor": mock_executor,
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [{"type": "function", "function": {"name": "loop_tool"}}],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Go"}],
            "info": mock_info,
        }

        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            result = await AIConversationService.chat_with_tools(
                user_id="user-123", content="Go", session=mock_session,
                info=mock_info, max_tool_iterations=2,
            )

        assert "Maximum tool iterations" in result["content"]
        assert result["tool_calls_count"] == 2

    @pytest.mark.asyncio
    async def test_tool_error_db_save_failure_does_not_cascade(self, mock_session, mock_info):
        """Test that a DB failure when saving tool error does not crash the agent loop."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        # add_tool_result raises to simulate DB failure
        mock_msg_service.add_tool_result = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_ai_service = AsyncMock()
        mock_executor = AsyncMock()

        tool_call_response = self._make_ai_response(
            content="",
            tool_calls=[{
                "id": "call-1",
                "function": {"name": "failing_tool", "arguments": "{}"},
            }],
        )
        final_response = self._make_ai_response("Done despite DB error.")

        mock_ai_service.chat_with_purpose = AsyncMock(
            side_effect=[tool_call_response, final_response]
        )
        mock_executor.execute = AsyncMock(
            side_effect=Exception("Tool execution failed")
        )

        ctx = {
            "executor": mock_executor,
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [{"type": "function", "function": {"name": "failing_tool"}}],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Do it"}],
            "info": mock_info,
        }

        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            result = await AIConversationService.chat_with_tools(
                user_id="user-123", content="Do it", session=mock_session,
                info=mock_info,
            )

        # Loop should complete successfully despite DB save failure
        assert result["content"] == "Done despite DB error."
        assert result["conversation_id"] == "conv-1"
        # DB save was attempted
        mock_msg_service.add_tool_result.assert_called_once()


# ========== chat_with_tools_streaming ==========


class TestChatWithToolsStreaming:
    """Tests for chat_with_tools_streaming."""

    @pytest.fixture
    def connected_user(self):
        return {"sub": "user-123", "is_super_user": False, "webservices": {}, "organizations": {}}

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_guard_rejects_missing_sub(self, mock_session):
        """Test that missing 'sub' claim raises ValueError."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        with pytest.raises(ValueError, match="connected_user must contain a valid 'sub' claim"):
            gen = AIConversationService.chat_with_tools_streaming(
                user_id="user-123",
                content="Hello",
                session=mock_session,
                connected_user={"is_super_user": False},  # No "sub"
                access_token="tok",
            )
            await gen.__anext__()

    @pytest.mark.asyncio
    async def test_guard_rejects_none_connected_user(self, mock_session):
        """Test that None connected_user raises ValueError."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        with pytest.raises(ValueError, match="connected_user must contain a valid 'sub' claim"):
            gen = AIConversationService.chat_with_tools_streaming(
                user_id="user-123",
                content="Hello",
                session=mock_session,
                connected_user=None,
                access_token="tok",
            )
            await gen.__anext__()

    @pytest.mark.asyncio
    async def test_guard_rejects_empty_access_token(self, mock_session, connected_user):
        """Test that empty access_token raises ValueError."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        with pytest.raises(ValueError, match="access_token is required"):
            gen = AIConversationService.chat_with_tools_streaming(
                user_id="user-123",
                content="Hello",
                session=mock_session,
                connected_user=connected_user,
                access_token="",
            )
            await gen.__anext__()

    @pytest.mark.asyncio
    async def test_simple_streaming_response(self, mock_session, connected_user):
        """Test streaming a simple text response with no tool calls."""
        from lys.apps.ai.modules.conversation.services import AIConversationService
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()

        async def fake_stream(*args, **kwargs):
            yield AIStreamChunk(content="Hello ", model="m1", provider="mistral")
            yield AIStreamChunk(content="world!", finish_reason="stop", usage={"prompt_tokens": 5, "completion_tokens": 2})

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = fake_stream

        ctx = {
            "executor": MagicMock(),
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Hi"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        events = []
        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for event in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Hi", session=mock_session,
                connected_user=connected_user, access_token="tok",
            ):
                events.append(event)

        # Should have 2 token events + 1 done event
        token_events = [e for e in events if "event: token" in e]
        done_events = [e for e in events if "event: done" in e]
        assert len(token_events) == 2
        assert len(done_events) == 1

        # Verify provider is dynamic, not hardcoded
        create_call = mock_msg_service.create.call_args
        assert create_call.kwargs.get("provider") == "mistral" or create_call[1].get("provider") == "mistral"

    @pytest.mark.asyncio
    async def test_provider_error_sanitized(self, mock_session, connected_user):
        """Test that streaming provider errors yield sanitized message to client."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        async def failing_stream(*args, **kwargs):
            raise ConnectionError("Internal network error: api-key=sk-secret123")
            yield  # pragma: no cover — makes this an async generator

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = failing_stream

        mock_msg_service = AsyncMock()
        ctx = {
            "executor": MagicMock(),
            "conversation": MagicMock(id="conv-1"),
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [],
            "messages": [{"role": "system", "content": "sys"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        events = []
        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for event in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Hi", session=mock_session,
                connected_user=connected_user, access_token="tok",
            ):
                events.append(event)

        # Should yield exactly one error event
        assert len(events) == 1
        error_data = json.loads(events[0].split("data: ")[1].strip())
        assert error_data["code"] == "PROVIDER_ERROR"
        # Must be generic, not containing the original error
        assert "An error occurred" in error_data["message"]
        assert "sk-secret" not in error_data["message"]
        assert "api-key" not in error_data["message"]
        # Orphaned user message should be deleted
        mock_msg_service.delete.assert_called_once_with("user-msg-1", mock_session)

    @pytest.mark.asyncio
    async def test_provider_error_delete_failure_still_yields_error_event(self, mock_session, connected_user):
        """Test that client receives error event even when orphaned message deletion fails."""
        from lys.apps.ai.modules.conversation.services import AIConversationService

        async def failing_stream(*args, **kwargs):
            raise ConnectionError("Provider down")
            yield  # pragma: no cover

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = failing_stream

        mock_msg_service = AsyncMock()
        mock_msg_service.delete.side_effect = Exception("DB connection lost")
        ctx = {
            "executor": MagicMock(),
            "conversation": MagicMock(id="conv-1"),
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [],
            "messages": [{"role": "system", "content": "sys"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        events = []
        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for event in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Hi", session=mock_session,
                connected_user=connected_user, access_token="tok",
            ):
                events.append(event)

        # Delete was attempted despite failure
        mock_msg_service.delete.assert_called_once_with("user-msg-1", mock_session)
        # Client still receives the error event
        assert len(events) == 1
        error_data = json.loads(events[0].split("data: ")[1].strip())
        assert error_data["code"] == "PROVIDER_ERROR"
        assert "An error occurred" in error_data["message"]

    @pytest.mark.asyncio
    async def test_tool_error_sanitized_in_stream(self, mock_session, connected_user):
        """Test that tool execution errors in streaming are sanitized."""
        from lys.apps.ai.modules.conversation.services import AIConversationService
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(
            side_effect=Exception("DB error: host=prod-db.internal password=p@ss")
        )

        call_count = 0

        async def fake_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First iteration: LLM requests a tool
                yield AIStreamChunk(
                    tool_calls=[{"index": 0, "id": "call-1", "function": {"name": "bad_tool", "arguments": "{}"}}],
                    finish_reason="tool_calls",
                    model="m1",
                    provider="test-provider",
                )
            else:
                # Second iteration: LLM responds after tool error
                yield AIStreamChunk(content="Sorry about that.", finish_reason="stop", model="m1", provider="test-provider")

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = fake_stream

        ctx = {
            "executor": mock_executor,
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [{"type": "function", "function": {"name": "bad_tool"}}],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Go"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        events = []
        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for event in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Go", session=mock_session,
                connected_user=connected_user, access_token="tok",
            ):
                events.append(event)

        # Find tool_result error event
        tool_result_events = [e for e in events if "event: tool_result" in e]
        assert len(tool_result_events) == 1
        error_data = json.loads(tool_result_events[0].split("data: ")[1].strip())
        assert error_data["success"] is False
        assert "failed to execute" in error_data["result"]["error"]
        # Must NOT contain sensitive info
        assert "password" not in error_data["result"]["error"]
        assert "prod-db" not in error_data["result"]["error"]

    @pytest.mark.asyncio
    async def test_tool_error_db_save_failure_does_not_cascade_stream(self, mock_session, connected_user):
        """Test that a DB failure when saving tool error does not crash the streaming loop."""
        from lys.apps.ai.modules.conversation.services import AIConversationService
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        # add_tool_result raises to simulate DB failure
        mock_msg_service.add_tool_result = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(
            side_effect=Exception("Tool execution failed")
        )

        call_count = 0

        async def fake_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield AIStreamChunk(
                    tool_calls=[{"index": 0, "id": "call-1", "function": {"name": "bad_tool", "arguments": "{}"}}],
                    finish_reason="tool_calls",
                    model="m1",
                    provider="test-provider",
                )
            else:
                yield AIStreamChunk(content="Recovered.", finish_reason="stop", model="m1", provider="test-provider")

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = fake_stream

        ctx = {
            "executor": mock_executor,
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [{"type": "function", "function": {"name": "bad_tool"}}],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Go"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        events = []
        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for event in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Go", session=mock_session,
                connected_user=connected_user, access_token="tok",
            ):
                events.append(event)

        # Streaming should complete despite DB save failure
        token_events = [e for e in events if "event: token" in e]
        done_events = [e for e in events if "event: done" in e]
        assert len(token_events) >= 1
        assert len(done_events) == 1
        # DB save was attempted
        mock_msg_service.add_tool_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_dynamic_provider_from_chunks(self, mock_session, connected_user):
        """Test that provider is read from stream chunks, not hardcoded."""
        from lys.apps.ai.modules.conversation.services import AIConversationService
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()

        async def fake_stream(*args, **kwargs):
            yield AIStreamChunk(content="Hi", model="custom-model", provider="openai")
            yield AIStreamChunk(content="!", finish_reason="stop", usage={"prompt_tokens": 5, "completion_tokens": 2})

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = fake_stream

        ctx = {
            "executor": MagicMock(),
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Hi"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for _ in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Hi", session=mock_session,
                connected_user=connected_user, access_token="tok",
            ):
                pass

        # Verify message was saved with dynamic provider, not "mistral"
        create_call = mock_msg_service.create.call_args
        assert create_call[1]["provider"] == "openai"
        assert create_call[1]["model"] == "custom-model"

    @pytest.mark.asyncio
    async def test_max_iterations_yields_error(self, mock_session, connected_user):
        """Test that max iterations yields MAX_ITERATIONS error event."""
        from lys.apps.ai.modules.conversation.services import AIConversationService
        from lys.apps.ai.utils.providers.abstracts import AIStreamChunk

        mock_conversation = MagicMock()
        mock_conversation.id = "conv-1"
        mock_msg_service = AsyncMock()
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"data": "ok"})

        async def tool_stream(*args, **kwargs):
            yield AIStreamChunk(
                tool_calls=[{"index": 0, "id": "call-1", "function": {"name": "loop", "arguments": "{}"}}],
                finish_reason="tool_calls",
                model="m1",
                provider="test",
            )

        mock_ai_service = MagicMock()
        mock_ai_service.chat_stream_with_purpose = tool_stream

        ctx = {
            "executor": mock_executor,
            "conversation": mock_conversation,
            "message_service": mock_msg_service,
            "ai_service": mock_ai_service,
            "llm_tools": [{"type": "function", "function": {"name": "loop"}}],
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "Go"}],
            "info": MagicMock(),
            "user_message_id": "user-msg-1",
        }

        events = []
        with patch.object(AIConversationService, "_prepare_chat_context", new_callable=AsyncMock, return_value=ctx):
            async for event in AIConversationService.chat_with_tools_streaming(
                user_id="user-123", content="Go", session=mock_session,
                connected_user=connected_user, access_token="tok",
                max_tool_iterations=1,
            ):
                events.append(event)

        # Last event should be the MAX_ITERATIONS error
        last_event = events[-1]
        assert "event: error" in last_event
        error_data = json.loads(last_event.split("data: ")[1].strip())
        assert error_data["code"] == "MAX_ITERATIONS"


class TestAIConversationServiceUsageFields:
    """Tests for AIConversationService._usage_fields token-column mapping."""

    def test_maps_all_usage_keys(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        assert AIConversationService._usage_fields({
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cache_read_tokens": 20,
            "cache_write_tokens": 30,
        }) == {
            "tokens_in": 10,
            "tokens_out": 5,
            "cache_read_tokens": 20,
            "cache_write_tokens": 30,
        }

    def test_none_usage_yields_all_none(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        assert AIConversationService._usage_fields(None) == {
            "tokens_in": None,
            "tokens_out": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }

    def test_missing_cache_keys_default_to_none(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        assert AIConversationService._usage_fields({
            "prompt_tokens": 7,
            "completion_tokens": 3,
        }) == {
            "tokens_in": 7,
            "tokens_out": 3,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }


def _role_msg(role, content=None, tool_calls=None, mid="m"):
    """Build a lightweight message stand-in with the attributes the service reads."""
    m = MagicMock()
    m.role = role
    m.content = content
    m.tool_calls = tool_calls
    m.id = mid
    return m


class TestComputeCompactionBoundary:
    """Tests for AIConversationService._compute_compaction_boundary."""

    def test_returns_none_when_within_window(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        msgs = [_role_msg(AIMessageRole.USER.value, mid=i) for i in range(5)]
        assert AIConversationService._compute_compaction_boundary(msgs, window=12) is None

    def test_boundary_is_message_before_window_start_on_user_frontier(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        # 6 messages, window=2 -> ideal_start=4 which is a user turn -> boundary = msgs[3].
        roles = [
            AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value,
            AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value,
            AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value,
        ]
        msgs = [_role_msg(r, mid=i) for i, r in enumerate(roles)]
        boundary = AIConversationService._compute_compaction_boundary(msgs, window=2)
        assert boundary is msgs[3]

    def test_snaps_forward_past_non_user_messages(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        # window=3 -> ideal_start=4 (assistant); snap forward to next user at idx 5 -> boundary msgs[4].
        roles = [
            AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value,
            AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value,
            AIMessageRole.ASSISTANT.value, AIMessageRole.USER.value,
            AIMessageRole.ASSISTANT.value,
        ]
        msgs = [_role_msg(r, mid=i) for i, r in enumerate(roles)]
        boundary = AIConversationService._compute_compaction_boundary(msgs, window=3)
        assert boundary is msgs[4]

    def test_returns_none_without_user_frontier_in_tail(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        # No user message at/after ideal_start (=4) -> no clean frontier -> None.
        roles = [
            AIMessageRole.USER.value, AIMessageRole.USER.value,
            AIMessageRole.USER.value, AIMessageRole.USER.value,
            AIMessageRole.ASSISTANT.value, AIMessageRole.ASSISTANT.value,
        ]
        msgs = [_role_msg(r, mid=i) for i, r in enumerate(roles)]
        assert AIConversationService._compute_compaction_boundary(msgs, window=2) is None


class TestRenderSummaryInput:
    """Tests for AIConversationService._render_summary_input."""

    def test_includes_prev_summary_and_folds_messages(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        msgs = [
            _role_msg(AIMessageRole.USER.value, content="hello"),
            _role_msg(AIMessageRole.ASSISTANT.value, content="hi there"),
            _role_msg(AIMessageRole.ASSISTANT.value, tool_calls=[{"function": {"name": "search"}}]),
            _role_msg(AIMessageRole.TOOL.value, content="big tool payload"),
        ]
        out = AIConversationService._render_summary_input("prior summary", msgs)
        assert "# Existing summary" in out
        assert "prior summary" in out
        assert "# New messages to fold in" in out
        assert "User: hello" in out
        assert "Assistant: hi there" in out
        assert "Assistant [used tools: search]" in out
        # Tool results are omitted from the summary input.
        assert "big tool payload" not in out

    def test_omits_existing_summary_section_without_prev(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        out = AIConversationService._render_summary_input(None, [_role_msg(AIMessageRole.USER.value, content="q")])
        assert "# Existing summary" not in out
        assert out.startswith("# New messages to fold in")


class TestMaybeEnqueueCompaction:
    """Tests for AIConversationService.maybe_enqueue_compaction (request-path trigger)."""

    @pytest.mark.asyncio
    async def test_below_threshold_is_noop(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        app_manager = MagicMock()
        app_manager.settings.get_plugin_config.return_value = {
            "chatbot": {"compaction": {"token_threshold": 1000}}
        }
        session = AsyncMock()
        conversation = MagicMock()
        conversation.id = "c1"

        with patch.object(AIConversationService, "app_manager", app_manager):
            await AIConversationService.maybe_enqueue_compaction(
                conversation, session, {"prompt_tokens": 100}
            )

        session.execute.assert_not_called()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_never_raises_on_internal_error(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        app_manager = MagicMock()
        app_manager.settings.get_plugin_config.side_effect = Exception("config boom")
        session = AsyncMock()
        conversation = MagicMock()
        conversation.id = "c1"

        with patch.object(AIConversationService, "app_manager", app_manager):
            # Must not propagate — a compaction failure may never break the turn.
            await AIConversationService.maybe_enqueue_compaction(
                conversation, session, {"prompt_tokens": 999999}
            )

    # The over-threshold enqueue path and the pending-summary guard build SQL range
    # predicates (created_at >= ...) over real columns; they are covered by integration
    # tests (tests/integration/apps/ai/test_conversation_service.py).


class TestFillSummary:
    """Tests for AIConversationService.fill_summary (synchronous worker body)."""

    def test_noop_when_row_missing_or_completed(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        app_manager = MagicMock()
        app_manager.get_entity.return_value = MagicMock()
        session = MagicMock()
        completed_row = MagicMock()
        completed_row.completed = True
        session.get.return_value = completed_row
        ai_service = MagicMock()

        with patch.object(AIConversationService, "app_manager", app_manager):
            AIConversationService.fill_summary(session, ai_service, "sum-1")

        ai_service.chat_with_purpose_sync.assert_not_called()

    def test_fills_row_with_summary_model_and_usage(self):
        from lys.apps.ai.modules.conversation import services as svc

        app_manager = MagicMock()
        summary_entity = MagicMock()
        message_entity = MagicMock()
        app_manager.get_entity.side_effect = lambda n: {
            "ai_conversation_summary": summary_entity,
            "ai_message": message_entity,
        }[n]

        row = MagicMock()
        row.completed = False
        row.conversation_id = "c1"
        row.through_message_id = "b1"

        session = MagicMock()
        # Summary row resolves to `row`; boundary message lookups return None so the
        # row-value range predicate (tuple_ comparison) is not built in this unit test —
        # the boundary windowing SQL is covered by integration tests.
        session.get.side_effect = lambda entity, ident: row if entity is summary_entity else None
        prev_result = MagicMock()
        prev_result.scalar_one_or_none.return_value = None  # no previous summary
        slice_result = MagicMock()
        slice_result.scalars.return_value.all.return_value = [
            _role_msg(AIMessageRole.USER.value, content="q"),
        ]
        session.execute.side_effect = [prev_result, slice_result]

        ai_service = MagicMock()
        response = MagicMock()
        response.content = "the summary"
        response.model = "claude-x"
        response.usage = {"prompt_tokens": 30, "completion_tokens": 8}
        ai_service.chat_with_purpose_sync.return_value = response

        with patch.object(svc.AIConversationService, "app_manager", app_manager), \
             patch.object(svc, "select", MagicMock()):
            svc.AIConversationService.fill_summary(session, ai_service, "sum-1")

        assert row.summary == "the summary"
        assert row.model == "claude-x"
        assert row.completed is True
        assert row.tokens_in == 30
        assert row.tokens_out == 8
        session.add.assert_called_with(row)


class TestDiscardPendingSummary:
    """Tests for discard_pending_summary / discard_pending_summary_sync."""

    @pytest.mark.asyncio
    async def test_async_deletes_uncompleted_row(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        app_manager = MagicMock()
        app_manager.get_entity.return_value = MagicMock()
        row = MagicMock()
        row.completed = False
        session = AsyncMock()
        session.get.return_value = row

        with patch.object(AIConversationService, "app_manager", app_manager):
            await AIConversationService.discard_pending_summary(session, "s1")

        session.delete.assert_awaited_once_with(row)

    @pytest.mark.asyncio
    async def test_async_keeps_completed_row(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        app_manager = MagicMock()
        app_manager.get_entity.return_value = MagicMock()
        row = MagicMock()
        row.completed = True
        session = AsyncMock()
        session.get.return_value = row

        with patch.object(AIConversationService, "app_manager", app_manager):
            await AIConversationService.discard_pending_summary(session, "s1")

        session.delete.assert_not_called()

    def test_sync_deletes_uncompleted_row(self):
        from lys.apps.ai.modules.conversation.services import AIConversationService

        app_manager = MagicMock()
        app_manager.get_entity.return_value = MagicMock()
        row = MagicMock()
        row.completed = False
        session = MagicMock()
        session.get.return_value = row

        with patch.object(AIConversationService, "app_manager", app_manager):
            AIConversationService.discard_pending_summary_sync(session, "s1")

        session.delete.assert_called_once_with(row)
