"""
Unit tests for AI app Celery tasks.

Tests Celery tasks with mocked dependencies.
"""

import inspect

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from lys.apps.ai.tasks import cleanup_old_ai_conversations


class TestCleanupOldAIConversationsTask:
    """Tests for cleanup_old_ai_conversations task."""

    def test_cleanup_task_has_default_hours_parameter(self):
        """Test that cleanup task has default hours=24."""
        sig = inspect.signature(cleanup_old_ai_conversations)
        assert "hours" in sig.parameters
        assert sig.parameters["hours"].default == 24

    def test_cleanup_task_accepts_custom_hours(self):
        """Test that cleanup task accepts hours parameter."""
        sig = inspect.signature(cleanup_old_ai_conversations)
        hours_param = sig.parameters["hours"]
        assert hours_param.annotation == int or hours_param.annotation == inspect.Parameter.empty

    def test_cleanup_old_ai_conversations_is_shared_task(self):
        """Test that cleanup_old_ai_conversations is decorated with @shared_task."""
        assert hasattr(cleanup_old_ai_conversations, "delay")
        assert hasattr(cleanup_old_ai_conversations, "apply_async")

    def test_cleanup_success(self):
        """Test successful cleanup returns deleted count."""
        mock_celery_app = MagicMock()
        mock_service = MagicMock()
        mock_celery_app.app_manager.get_service.return_value = mock_service

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_service.delete_old_conversations = AsyncMock(return_value=5)

        with patch("lys.apps.ai.tasks.current_app", mock_celery_app), \
             patch("lys.core.managers.database.DatabaseManager") as MockDB:
            MockDB.async_session.return_value = mock_session
            result = cleanup_old_ai_conversations(hours=48)

        assert result == 5
        mock_celery_app.app_manager.get_service.assert_called_once_with("ai_conversation")

    def test_cleanup_failure_returns_zero(self):
        """Test that cleanup returns 0 on async failure."""
        mock_celery_app = MagicMock()
        mock_service = MagicMock()
        mock_celery_app.app_manager.get_service.return_value = mock_service
        mock_service.delete_old_conversations = AsyncMock(
            side_effect=Exception("Database error")
        )

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("lys.apps.ai.tasks.current_app", mock_celery_app), \
             patch("lys.core.managers.database.DatabaseManager") as MockDB:
            MockDB.async_session.return_value = mock_session
            result = cleanup_old_ai_conversations()

        assert result == 0

    def test_cleanup_uses_logger_not_print(self):
        """Test that cleanup uses logger instead of print."""
        import ast
        import lys.apps.ai.tasks as tasks_module
        source = inspect.getsource(tasks_module)
        tree = ast.parse(source)

        # Check no print() calls exist in the module
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    pytest.fail("Found print() call in ai/tasks.py - should use logger")