"""
Unit tests for user_auth event tasks (Phase 7.9).

Tests trigger_event Celery task:
- Critical email path (emailing_id provided)
- Non-critical email path (batch dispatch)
- Notification path
- Unknown event type
- Retry on failure
- Combined email + notification
"""
from unittest.mock import Mock, MagicMock, patch

import pytest

from lys.apps.user_auth.modules.event.tasks import trigger_event


def _setup_app_manager(mock_current_app, services_map):
    """Helper to setup app_manager mock with services."""
    am = MagicMock()
    mock_current_app.app_manager = am

    def get_service(name):
        return services_map.get(name, Mock())

    am.get_service.side_effect = get_service

    mock_session = MagicMock()
    am.database.get_sync_session.return_value.__enter__ = Mock(return_value=mock_session)
    am.database.get_sync_session.return_value.__exit__ = Mock(return_value=False)

    return am, mock_session


class TestTriggerEventTask:
    """Tests for trigger_event Celery task."""

    def test_task_exists(self):
        assert trigger_event is not None

    def test_task_is_callable(self):
        assert callable(trigger_event)

    def test_task_has_delay_attribute(self):
        """Celery tasks should have a .delay method."""
        assert hasattr(trigger_event, "delay")


class TestTriggerEventCriticalEmail:
    """Tests for critical email path (emailing_id provided)."""

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_critical_email_calls_send_email(self, mock_current_app):
        """When emailing_id is provided, send_email is called directly."""
        emailing_service = Mock()
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": False}
        }

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing": emailing_service,
        })

        result = trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
            emailing_id="email-123",
        )

        emailing_service.send_email.assert_called_once_with("email-123")
        assert result["email_sent"] is True

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_critical_email_retries_on_failure(self, mock_current_app):
        """When send_email fails, the task retries."""
        emailing_service = Mock()
        emailing_service.send_email.side_effect = RuntimeError("SMTP down")

        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": False}
        }

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing": emailing_service,
        })

        with patch.object(trigger_event, "retry", side_effect=RuntimeError("retry")):
            with pytest.raises(RuntimeError, match="retry"):
                trigger_event.run(
                    event_type="TEST_EVENT",
                    user_id="user-1",
                    emailing_id="email-123",
                )

            trigger_event.retry.assert_called_once()


class TestTriggerEventBatchEmail:
    """Tests for non-critical batch email path."""

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_batch_email_calls_dispatch_sync(self, mock_current_app):
        """Without emailing_id, dispatch_sync is called for batch emails."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": False}
        }
        event_service.should_send.return_value = True

        batch_service = Mock()
        batch_service.dispatch_sync.return_value = ["email-1", "email-2"]

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing_batch": batch_service,
        })

        result = trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
            email_context={"key": "val"},
            organization_data={"client_ids": ["c1"]},
        )

        batch_service.dispatch_sync.assert_called_once()
        call_kwargs = batch_service.dispatch_sync.call_args.kwargs
        assert call_kwargs["type_id"] == "TEST_EVENT"
        assert call_kwargs["email_context"] == {"key": "val"}
        assert call_kwargs["triggered_by_user_id"] == "user-1"
        assert call_kwargs["organization_data"] == {"client_ids": ["c1"]}
        assert result["email_sent"] is True

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_batch_email_not_sent_when_disabled(self, mock_current_app):
        """When config has email=False, no email is sent."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": False, "notification": False}
        }

        _setup_app_manager(mock_current_app, {"event": event_service})

        result = trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
        )

        assert result["email_sent"] is False

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_batch_email_empty_result_not_marked_sent(self, mock_current_app):
        """When dispatch_sync returns empty list, email_sent stays False."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": False}
        }
        event_service.should_send.return_value = True

        batch_service = Mock()
        batch_service.dispatch_sync.return_value = []

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing_batch": batch_service,
        })

        result = trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
        )

        assert result["email_sent"] is False

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_batch_email_retries_on_failure(self, mock_current_app):
        """When dispatch_sync fails, the task retries."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": False}
        }

        batch_service = Mock()
        batch_service.dispatch_sync.side_effect = RuntimeError("DB error")

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing_batch": batch_service,
        })

        with patch.object(trigger_event, "retry", side_effect=RuntimeError("retry")):
            with pytest.raises(RuntimeError, match="retry"):
                trigger_event.run(
                    event_type="TEST_EVENT",
                    user_id="user-1",
                )

            trigger_event.retry.assert_called_once()


class TestTriggerEventNotification:
    """Tests for notification dispatch path."""

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_notification_dispatched(self, mock_current_app):
        """When notification=True, notification_batch_service.dispatch_sync is called."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": False, "notification": True}
        }
        event_service.should_send.return_value = True

        notification_batch = Mock()

        _, mock_session = _setup_app_manager(mock_current_app, {
            "event": event_service,
            "notification_batch": notification_batch,
        })

        result = trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
            notification_data={"title": "Hello"},
            organization_data={"client_ids": ["c1"]},
            additional_user_ids=["user-2"],
        )

        notification_batch.dispatch_sync.assert_called_once()
        call_kwargs = notification_batch.dispatch_sync.call_args.kwargs
        assert call_kwargs["type_id"] == "TEST_EVENT"
        assert call_kwargs["data"] == {"title": "Hello"}
        assert call_kwargs["triggered_by_user_id"] == "user-1"
        assert call_kwargs["organization_data"] == {"client_ids": ["c1"]}
        assert call_kwargs["additional_user_ids"] == ["user-2"]
        assert result["notification_sent"] is True

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_notification_retries_on_failure(self, mock_current_app):
        """When notification dispatch fails, the task retries."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": False, "notification": True}
        }

        notification_batch = Mock()
        notification_batch.dispatch_sync.side_effect = RuntimeError("fail")

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "notification_batch": notification_batch,
        })

        with patch.object(trigger_event, "retry", side_effect=RuntimeError("retry")):
            with pytest.raises(RuntimeError, match="retry"):
                trigger_event.run(
                    event_type="TEST_EVENT",
                    user_id="user-1",
                    notification_data={"title": "Hello"},
                )

            trigger_event.retry.assert_called_once()


class TestTriggerEventCombined:
    """Tests for combined email + notification scenarios."""

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_both_email_and_notification(self, mock_current_app):
        """When both email and notification are enabled, both are dispatched."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": True}
        }
        event_service.should_send.return_value = True

        batch_service = Mock()
        batch_service.dispatch_sync.return_value = ["email-1"]

        notification_batch = Mock()

        _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing_batch": batch_service,
            "notification_batch": notification_batch,
        })

        result = trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
            email_context={"key": "val"},
            notification_data={"title": "Hello"},
        )

        batch_service.dispatch_sync.assert_called_once()
        notification_batch.dispatch_sync.assert_called_once()
        assert result["email_sent"] is True
        assert result["notification_sent"] is True

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_unknown_event_type_raises(self, mock_current_app):
        """Unknown event_type raises ValueError."""
        event_service = Mock()
        event_service.get_channels.return_value = {}

        _setup_app_manager(mock_current_app, {"event": event_service})

        with pytest.raises(ValueError, match="Unknown event type"):
            trigger_event.run(
                event_type="NONEXISTENT_EVENT",
                user_id="user-1",
            )

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_should_send_fn_passed_to_batch(self, mock_current_app):
        """The should_send callback wraps event_service.should_send."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": True, "notification": False}
        }
        event_service.should_send.return_value = True

        batch_service = Mock()
        batch_service.dispatch_sync.return_value = ["e1"]

        _, mock_session = _setup_app_manager(mock_current_app, {
            "event": event_service,
            "emailing_batch": batch_service,
        })

        trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
        )

        # Verify should_send_fn was passed
        call_kwargs = batch_service.dispatch_sync.call_args.kwargs
        should_send_fn = call_kwargs["should_send_fn"]
        assert callable(should_send_fn)

        # Call it to verify it delegates to event_service.should_send
        should_send_fn("user-2")
        event_service.should_send.assert_called_with(
            "user-2", "TEST_EVENT", "email", mock_session
        )

    @patch("lys.apps.user_auth.modules.event.tasks.current_app")
    def test_session_committed_at_end(self, mock_current_app):
        """The session is committed after all operations."""
        event_service = Mock()
        event_service.get_channels.return_value = {
            "TEST_EVENT": {"email": False, "notification": False}
        }

        _, mock_session = _setup_app_manager(mock_current_app, {
            "event": event_service,
        })

        trigger_event.run(
            event_type="TEST_EVENT",
            user_id="user-1",
        )

        mock_session.commit.assert_called_once()
