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

    def test_send_pending_email_failure_retries(self, mock_celery_app, mock_emailing_service):
        """Test email sending failure triggers retry."""
        from lys.apps.base.tasks import send_pending_email

        mock_celery_app.app_manager.get_service.return_value = mock_emailing_service
        mock_emailing_service.send_email.side_effect = Exception("SMTP error")

        with patch('lys.apps.base.tasks.current_app', mock_celery_app):
            with patch.object(send_pending_email, 'retry', side_effect=Exception("retry")) as mock_retry:
                with pytest.raises(Exception, match="retry"):
                    send_pending_email.run("email-456")

                mock_retry.assert_called_once()

    def test_send_pending_email_gets_service_from_app_manager(self, mock_celery_app, mock_emailing_service):
        """Test that emailing service is retrieved from app_manager."""
        from lys.apps.base.tasks import send_pending_email

        mock_celery_app.app_manager.get_service.return_value = mock_emailing_service

        with patch('lys.apps.base.tasks.current_app', mock_celery_app):
            send_pending_email("email-789")

        mock_celery_app.app_manager.get_service.assert_called_once_with("emailing")


class TestTaskDecorators:
    """Tests for task decorators and structure."""

    def test_send_pending_email_is_shared_task(self):
        """Test that send_pending_email is decorated with @shared_task."""
        from lys.apps.base.tasks import send_pending_email

        # shared_task adds certain attributes
        assert hasattr(send_pending_email, 'delay')
        assert hasattr(send_pending_email, 'apply_async')
