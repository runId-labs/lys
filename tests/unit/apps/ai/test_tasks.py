"""
Unit tests for AI app Celery tasks.

Tests Celery tasks with mocked dependencies.
"""

import ast
import inspect

from unittest.mock import MagicMock, patch

import pytest

from lys.apps.ai.tasks import summarize_conversation


def _mock_current_app():
    """Build a mock current_app whose app_manager exposes a sync-session context manager."""
    current_app = MagicMock()
    conversation_service = MagicMock()
    ai_service = MagicMock()
    current_app.app_manager.get_service.side_effect = lambda name: {
        "ai_conversation": conversation_service,
        "ai": ai_service,
    }[name]

    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__enter__.return_value = session
    session_cm.__exit__.return_value = False
    current_app.app_manager.database.get_sync_session.return_value = session_cm

    return current_app, conversation_service, ai_service, session


class TestSummarizeConversationTask:
    """Tests for the summarize_conversation Celery task."""

    def test_is_shared_task(self):
        """The task is decorated with @shared_task (exposes delay / apply_async)."""
        assert hasattr(summarize_conversation, "delay")
        assert hasattr(summarize_conversation, "apply_async")

    def test_takes_summary_id_parameter(self):
        sig = inspect.signature(summarize_conversation)
        assert "summary_id" in sig.parameters

    def test_success_fills_summary_and_returns_true(self):
        """On success the task calls fill_summary(session, ai_service, id) and returns True."""
        current_app, conv_service, ai_service, session = _mock_current_app()

        with patch("lys.apps.ai.tasks.current_app", current_app):
            result = summarize_conversation("sum-1")

        assert result is True
        conv_service.fill_summary.assert_called_once_with(session, ai_service, "sum-1")
        conv_service.discard_pending_summary_sync.assert_not_called()

    def test_failure_discards_pending_and_returns_false(self):
        """If fill_summary raises, the pending row is discarded and the task returns False."""
        current_app, conv_service, ai_service, session = _mock_current_app()
        conv_service.fill_summary.side_effect = Exception("provider down")

        with patch("lys.apps.ai.tasks.current_app", current_app):
            result = summarize_conversation("sum-1")

        assert result is False
        conv_service.discard_pending_summary_sync.assert_called_once_with(session, "sum-1")

    def test_failure_swallows_discard_error_and_returns_false(self):
        """A failure while discarding the pending row must not propagate."""
        current_app, conv_service, ai_service, session = _mock_current_app()
        conv_service.fill_summary.side_effect = Exception("provider down")
        conv_service.discard_pending_summary_sync.side_effect = Exception("db gone")

        with patch("lys.apps.ai.tasks.current_app", current_app):
            result = summarize_conversation("sum-1")

        assert result is False

    def test_no_print_calls_in_module(self):
        """The task module logs via logger, never print()."""
        import lys.apps.ai.tasks as tasks_module

        tree = ast.parse(inspect.getsource(tasks_module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    pytest.fail("Found print() call in ai/tasks.py - should use logger")
