"""
Unit tests for base app Celery tasks.

Tests Celery tasks with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestSendPendingEmailTask:
    """Tests for send_pending_email task."""

    @pytest.fixture
    def mock_celery_app(self):
        """Create mock Celery app with app_manager."""
        celery_app = MagicMock()
        celery_app.app_manager = MagicMock()
        return celery_app

    @pytest.fixture
    def mock_emailing_service(self):
        """Create mock emailing service."""
        return MagicMock()

    def test_send_pending_email_success(self, mock_celery_app, mock_emailing_service):
        """Test successful email sending."""
        from lys.apps.base.tasks import send_pending_email

        mock_celery_app.app_manager.get_service.return_value = mock_emailing_service
        mock_emailing_service.send_email.return_value = None

        with patch('lys.apps.base.tasks.current_app', mock_celery_app):
            result = send_pending_email("email-123")

        mock_emailing_service.send_email.assert_called_once_with("email-123")
        assert result is True

    def test_send_pending_email_failure(self, mock_celery_app, mock_emailing_service):
        """Test email sending failure."""
        from lys.apps.base.tasks import send_pending_email

        mock_celery_app.app_manager.get_service.return_value = mock_emailing_service
        mock_emailing_service.send_email.side_effect = Exception("SMTP error")

        with patch('lys.apps.base.tasks.current_app', mock_celery_app):
            result = send_pending_email("email-456")

        assert result is False

    def test_send_pending_email_gets_service_from_app_manager(self, mock_celery_app, mock_emailing_service):
        """Test that emailing service is retrieved from app_manager."""
        from lys.apps.base.tasks import send_pending_email

        mock_celery_app.app_manager.get_service.return_value = mock_emailing_service

        with patch('lys.apps.base.tasks.current_app', mock_celery_app):
            send_pending_email("email-789")

        mock_celery_app.app_manager.get_service.assert_called_once_with("emailing")


class TestCleanupOldAIConversationsTask:
    """Tests for cleanup_old_ai_conversations task.

    Note: Full execution testing requires Celery worker context and database.
    These tests verify task structure and parameter handling.
    """

    def test_cleanup_task_has_default_hours_parameter(self):
        """Test that cleanup task has default hours=24."""
        from lys.apps.base.tasks import cleanup_old_ai_conversations
        import inspect

        sig = inspect.signature(cleanup_old_ai_conversations)
        assert 'hours' in sig.parameters
        assert sig.parameters['hours'].default == 24

    def test_cleanup_task_accepts_custom_hours(self):
        """Test that cleanup task accepts hours parameter."""
        from lys.apps.base.tasks import cleanup_old_ai_conversations
        import inspect

        sig = inspect.signature(cleanup_old_ai_conversations)
        hours_param = sig.parameters['hours']
        assert hours_param.annotation == int or hours_param.annotation == inspect.Parameter.empty


class TestTaskDecorators:
    """Tests for task decorators and structure."""

    def test_send_pending_email_is_shared_task(self):
        """Test that send_pending_email is decorated with @shared_task."""
        from lys.apps.base.tasks import send_pending_email

        # shared_task adds certain attributes
        assert hasattr(send_pending_email, 'delay')
        assert hasattr(send_pending_email, 'apply_async')

    def test_cleanup_old_ai_conversations_is_shared_task(self):
        """Test that cleanup_old_ai_conversations is decorated with @shared_task."""
        from lys.apps.base.tasks import cleanup_old_ai_conversations

        assert hasattr(cleanup_old_ai_conversations, 'delay')
        assert hasattr(cleanup_old_ai_conversations, 'apply_async')
