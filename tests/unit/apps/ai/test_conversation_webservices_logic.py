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

    def test_tool_answers_are_passed_and_the_call_id_returned(self):
        """The answers reach the service; a proposal's toolCallId reaches the client."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        original_init = _make_node_constructable(AIMessageNode)
        try:
            resolver = self._get_resolver()

            answers = [MagicMock()]
            mock_inputs = MagicMock()
            mock_input_data = MagicMock()
            mock_input_data.conversation_id = "conv-123"
            mock_input_data.message = None
            mock_input_data.context = None
            mock_input_data.tool_answers = answers
            mock_inputs.to_pydantic.return_value = mock_input_data

            mock_info = MagicMock()
            mock_info.context.connected_user = {"sub": "user-uuid"}
            mock_info.context.session = AsyncMock()

            mock_conv_service = MagicMock()
            mock_conv_service.chat_with_tools = AsyncMock(return_value={
                "content": "Je te propose ceci.",
                "conversation_id": "conv-123",
                "tool_calls_count": 1,
                "tool_results": None,
                "frontend_actions": [{"type": "thing_proposal", "toolCallId": "call-1"}],
            })
            mock_info.context.app_manager.get_service.return_value = mock_conv_service

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(None, inputs=mock_inputs, info=mock_info))
            finally:
                loop.close()

            assert mock_conv_service.chat_with_tools.await_args.kwargs["tool_answers"] is answers
            assert result.frontend_actions[0].tool_call_id == "call-1"
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


def _get_edition_resolver(cls, method_name):
    """Extract the raw business-logic function `lys_edition` wraps.

    `_edition_resolver_generator` (lys/core/graphql/edit.py) closes over the original
    method as `resolver`; the wrapper it produces (`inner_resolver`) does the id lookup
    and access check, then awaits this raw resolver with the already-fetched `obj`. Same
    technique as TestSendAiMessageLogic._get_resolver, applied to lys_edition instead of
    lys_field.
    """
    wrapped = cls.__dict__[method_name]
    idx = wrapped.__code__.co_freevars.index("resolver")
    return wrapped.__closure__[idx].cell_contents


class TestUpdateAIConversationTitleLogic:
    """Tests for AIConversationMutation.update_ai_conversation_title() internal logic."""

    def test_sets_title_from_the_pydantic_input_and_returns_the_object(self):
        from lys.apps.ai.modules.conversation.webservices import AIConversationMutation

        resolver = _get_edition_resolver(AIConversationMutation, "update_ai_conversation_title")

        obj = MagicMock()
        inputs = MagicMock()
        inputs.to_pydantic.return_value.title = "Budget review"

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                resolver(None, obj=obj, inputs=inputs, info=MagicMock())
            )
        finally:
            loop.close()

        assert result is obj
        assert obj.title == "Budget review"


class TestVisibilityFlagMutationsLogic:
    """Tests for the visibility flag mutations.

    The flag rules themselves live in the service (archive/unarchive/pin/unpin -
    see test_conversation_services.py); what these resolvers own is the delegation:
    the conversation resolved and owned-checked by lys_edition is handed to the
    registered service, and its result is what the caller receives.
    """

    def _call_with_service(self, method_name, service_result=None):
        from lys.apps.ai.modules.conversation.webservices import AIConversationMutation

        resolver = _get_edition_resolver(AIConversationMutation, method_name)
        conversation_service = AsyncMock()
        conversation_service.archive.return_value = service_result
        conversation_service.unarchive.return_value = service_result
        conversation_service.pin.return_value = service_result
        conversation_service.unpin.return_value = service_result

        obj = MagicMock()
        info = MagicMock()
        info.context.app_manager.get_service.return_value = conversation_service

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(resolver(None, obj=obj, info=info))
        finally:
            loop.close()

        return obj, info, conversation_service, result

    def test_archive_delegates_to_the_service(self):
        obj, info, conversation_service, result = self._call_with_service(
            "archive_ai_conversation", service_result="archived"
        )
        conversation_service.archive.assert_called_once_with(obj, info.context.session)
        assert result == "archived"

    def test_unarchive_delegates_to_the_service(self):
        obj, info, conversation_service, result = self._call_with_service(
            "unarchive_ai_conversation", service_result="restored"
        )
        conversation_service.unarchive.assert_called_once_with(obj, info.context.session)
        assert result == "restored"

    def test_pin_delegates_to_the_service(self):
        obj, info, conversation_service, result = self._call_with_service(
            "pin_ai_conversation", service_result="pinned"
        )
        conversation_service.pin.assert_called_once_with(obj, info.context.session)
        assert result == "pinned"

    def test_unpin_delegates_to_the_service(self):
        obj, info, conversation_service, result = self._call_with_service(
            "unpin_ai_conversation", service_result="unpinned"
        )
        conversation_service.unpin.assert_called_once_with(obj, info.context.session)
        assert result == "unpinned"


class TestAllAIConversationsFilterLogic:
    """Tests for AIConversationQuery.all_ai_conversations() archived/pinned filters."""

    @staticmethod
    def _run(**kwargs):
        """Run the raw listing resolver on a mocked entity and statement chain.

        `select` and `noload` are patched because entity classes are not mapped in unit
        tests; the statement mock returns itself from every builder call so each `where`
        is recorded on it.
        """
        from lys.apps.ai.modules.conversation.webservices import AIConversationQuery

        resolver = _get_edition_resolver(AIConversationQuery, "all_ai_conversations")

        entity = MagicMock()
        info = MagicMock()
        info.context.app_manager.get_entity.return_value = entity

        stmt = MagicMock()
        stmt.options.return_value = stmt
        stmt.order_by.return_value = stmt
        stmt.where.return_value = stmt

        module = "lys.apps.ai.modules.conversation.webservices"
        with patch(f"{module}.select", return_value=stmt), patch(f"{module}.noload"):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(None, info, **kwargs))
            finally:
                loop.close()

        assert result is stmt
        return entity, stmt

    def test_default_lists_active_conversations_and_ignores_the_pin(self):
        entity, stmt = self._run()

        stmt.where.assert_called_once_with(entity.archived_at.is_.return_value)
        entity.archived_at.is_.assert_called_once_with(None)
        entity.pinned_at.isnot.assert_not_called()
        entity.pinned_at.is_.assert_not_called()

    def test_archived_true_lists_the_archive_alone(self):
        entity, stmt = self._run(archived=True)

        stmt.where.assert_called_once_with(entity.archived_at.isnot.return_value)
        entity.archived_at.isnot.assert_called_once_with(None)

    def test_archived_null_applies_no_archive_filter(self):
        entity, stmt = self._run(archived=None)

        stmt.where.assert_not_called()

    def test_pinned_true_lists_only_pinned_conversations(self):
        entity, stmt = self._run(archived=None, pinned=True)

        stmt.where.assert_called_once_with(entity.pinned_at.isnot.return_value)
        entity.pinned_at.isnot.assert_called_once_with(None)

    def test_pinned_false_lists_only_unpinned_conversations(self):
        entity, stmt = self._run(archived=None, pinned=False)

        stmt.where.assert_called_once_with(entity.pinned_at.is_.return_value)
        entity.pinned_at.is_.assert_called_once_with(None)

    def test_pinned_and_archived_filters_combine(self):
        """Pin and archive are orthogonal: both filters apply side by side."""
        entity, stmt = self._run(archived=True, pinned=True)

        assert stmt.where.call_count == 2
        stmt.where.assert_any_call(entity.archived_at.isnot.return_value)
        stmt.where.assert_any_call(entity.pinned_at.isnot.return_value)
