"""
Unit tests for AI conversation webservices logic.

Tests the send_ai_message resolver logic directly, bypassing the lys_field wrapper.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


def _make_node_constructable(cls):
    """Patch a ServiceNode subclass to accept kwargs in __init__.

    Strawberry @type decorator adds __init__ at schema build time,
    which hasn't happened in unit tests. This adds a simple kwargs-based init.
    """
    original_init = cls.__init__

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    cls.__init__ = __init__
    return original_init


class TestSendAiMessageLogic:
    """Tests for send_ai_message() internal logic."""

    def _get_resolver(self):
        """Import and get the raw resolver function.

        lys_field wraps the original function in an inner_resolver closure.
        The original resolver is stored in the closure as 'resolver' freevar.
        """
        from lys.apps.ai.modules.conversation.webservices import AIMutation
        wrapped = AIMutation.__dict__["send_ai_message"]
        idx = wrapped.__code__.co_freevars.index("resolver")
        return wrapped.__closure__[idx].cell_contents

    def test_unauthenticated_user_returns_error_message(self):
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        original_init = _make_node_constructable(AIMessageNode)
        try:
            resolver = self._get_resolver()

            mock_inputs = MagicMock()
            mock_input_data = MagicMock()
            mock_input_data.conversation_id = "conv-123"
            mock_input_data.message = "Hello"
            mock_input_data.context = None
            mock_inputs.to_pydantic.return_value = mock_input_data

            mock_info = MagicMock()
            mock_info.context.connected_user = None

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(None, inputs=mock_inputs, info=mock_info))
            finally:
                loop.close()

            assert "authenticated" in result.content.lower()
            assert result.tool_calls_count == 0
        finally:
            AIMessageNode.__init__ = original_init

    def test_authenticated_user_calls_conversation_service(self):
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        original_init = _make_node_constructable(AIMessageNode)
        try:
            resolver = self._get_resolver()

            mock_inputs = MagicMock()
            mock_input_data = MagicMock()
            mock_input_data.conversation_id = "conv-123"
            mock_input_data.message = "Hello AI"
            mock_input_data.context = None
            mock_inputs.to_pydantic.return_value = mock_input_data

            mock_info = MagicMock()
            mock_info.context.connected_user = {"sub": "user-uuid"}
            mock_info.context.session = AsyncMock()

            mock_conv_service = MagicMock()
            mock_conv_service.chat_with_tools = AsyncMock(return_value={
                "content": "Hello! How can I help?",
                "conversation_id": "conv-123",
                "tool_calls_count": 0,
                "tool_results": None,
                "frontend_actions": None,
            })
            mock_info.context.app_manager.get_service.return_value = mock_conv_service

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(None, inputs=mock_inputs, info=mock_info))
            finally:
                loop.close()

            assert result.content == "Hello! How can I help?"
            assert result.conversation_id == "conv-123"
            mock_conv_service.chat_with_tools.assert_called_once()
        finally:
            AIMessageNode.__init__ = original_init

    def test_response_with_tool_results(self):
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        original_init = _make_node_constructable(AIMessageNode)
        try:
            resolver = self._get_resolver()

            mock_inputs = MagicMock()
            mock_input_data = MagicMock()
            mock_input_data.conversation_id = "conv-123"
            mock_input_data.message = "List users"
            mock_input_data.context = None
            mock_inputs.to_pydantic.return_value = mock_input_data

            mock_info = MagicMock()
            mock_info.context.connected_user = {"sub": "user-uuid"}
            mock_info.context.session = AsyncMock()

            mock_conv_service = MagicMock()
            mock_conv_service.chat_with_tools = AsyncMock(return_value={
                "content": "Found 3 users",
                "conversation_id": "conv-123",
                "tool_calls_count": 1,
                "tool_results": [
                    {"tool_name": "all_users", "result": "[...]", "success": True}
                ],
                "frontend_actions": [
                    {"type": "navigate", "path": "/users"}
                ],
            })
            mock_info.context.app_manager.get_service.return_value = mock_conv_service

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(None, inputs=mock_inputs, info=mock_info))
            finally:
                loop.close()

            assert result.tool_calls_count == 1
            assert result.tool_results is not None
            assert len(result.tool_results) == 1
            assert result.tool_results[0].tool_name == "all_users"
            assert result.frontend_actions is not None
            assert len(result.frontend_actions) == 1
            assert result.frontend_actions[0].type == "navigate"
        finally:
            AIMessageNode.__init__ = original_init

    def test_user_with_empty_sub_returns_error(self):
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        original_init = _make_node_constructable(AIMessageNode)
        try:
            resolver = self._get_resolver()

            mock_inputs = MagicMock()
            mock_input_data = MagicMock()
            mock_input_data.conversation_id = None
            mock_input_data.message = "Hello"
            mock_input_data.context = None
            mock_inputs.to_pydantic.return_value = mock_input_data

            mock_info = MagicMock()
            mock_info.context.connected_user = {"sub": None}

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(None, inputs=mock_inputs, info=mock_info))
            finally:
                loop.close()

            assert "authenticated" in result.content.lower()
        finally:
            AIMessageNode.__init__ = original_init
