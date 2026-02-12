"""
Unit tests for EmailingBatchService.

Tests:
- Class structure and inheritance
- Method signatures (dispatch, dispatch_sync)
- Private_data enrichment logic in _create_emails_sync
- should_send_fn filtering
"""
import inspect
from unittest.mock import Mock, MagicMock, patch, AsyncMock

import pytest

from lys.apps.base.mixins.recipient_resolution import RecipientResolutionMixin
from lys.apps.base.modules.emailing.services import EmailingBatchService
from lys.core.services import Service


class TestEmailingBatchServiceStructure:
    """Verify class structure and inheritance."""

    def test_class_exists(self):
        assert inspect.isclass(EmailingBatchService)

    def test_inherits_from_service(self):
        assert issubclass(EmailingBatchService, Service)

    def test_inherits_from_recipient_resolution_mixin(self):
        assert issubclass(EmailingBatchService, RecipientResolutionMixin)

    def test_service_name(self):
        assert EmailingBatchService.service_name == "emailing_batch"

    def test_has_dispatch(self):
        assert hasattr(EmailingBatchService, "dispatch")

    def test_dispatch_is_async(self):
        assert inspect.iscoroutinefunction(EmailingBatchService.dispatch)

    def test_dispatch_is_classmethod(self):
        assert isinstance(
            inspect.getattr_static(EmailingBatchService, "dispatch"), classmethod
        )

    def test_has_dispatch_sync(self):
        assert hasattr(EmailingBatchService, "dispatch_sync")

    def test_dispatch_sync_is_sync(self):
        assert not inspect.iscoroutinefunction(EmailingBatchService.dispatch_sync)

    def test_dispatch_sync_is_classmethod(self):
        assert isinstance(
            inspect.getattr_static(EmailingBatchService, "dispatch_sync"), classmethod
        )

    def test_has_create_emails(self):
        assert hasattr(EmailingBatchService, "_create_emails")

    def test_create_emails_is_async(self):
        assert inspect.iscoroutinefunction(EmailingBatchService._create_emails)

    def test_has_create_emails_sync(self):
        assert hasattr(EmailingBatchService, "_create_emails_sync")

    def test_create_emails_sync_is_sync(self):
        assert not inspect.iscoroutinefunction(EmailingBatchService._create_emails_sync)


class TestDispatchSignature:
    """Verify dispatch method signatures."""

    def test_dispatch_params(self):
        sig = inspect.signature(EmailingBatchService.dispatch)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "type_id" in params
        assert "email_context" in params
        assert "triggered_by_user_id" in params
        assert "additional_user_ids" in params
        assert "should_send_fn" in params

    def test_dispatch_sync_params(self):
        sig = inspect.signature(EmailingBatchService.dispatch_sync)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "type_id" in params
        assert "email_context" in params
        assert "triggered_by_user_id" in params
        assert "additional_user_ids" in params
        assert "should_send_fn" in params

    def test_dispatch_email_context_default_none(self):
        sig = inspect.signature(EmailingBatchService.dispatch)
        assert sig.parameters["email_context"].default is None

    def test_dispatch_should_send_fn_default_none(self):
        sig = inspect.signature(EmailingBatchService.dispatch)
        assert sig.parameters["should_send_fn"].default is None


class TestCreateAndSendEmailsSyncLogic:
    """Tests for _create_emails_sync creation and filtering logic."""

    def _setup_mocks(self):
        """Set up common mocks for create_and_send tests."""
        # Mock user with private_data
        user = Mock()
        user.email_address = Mock()
        user.email_address.id = "test@example.com"
        user.language_id = "en"
        user.private_data = Mock()
        user.private_data.first_name = "Alice"
        user.private_data.last_name = "Smith"

        # Mock entities and services
        user_entity = Mock()
        emailing_service = Mock()
        emailing_entity = Mock()
        emailing_service.entity_class = emailing_entity
        emailing_instance = Mock()
        emailing_instance.id = "emailing-1"
        emailing_entity.return_value = emailing_instance

        # Mock app_manager
        app_manager = Mock()
        app_manager.get_entity.return_value = user_entity
        app_manager.get_service.return_value = emailing_service

        # Mock session
        session = Mock()
        session.get.return_value = user

        return app_manager, session, user, emailing_service, emailing_instance

    def test_private_data_enriched_in_context(self):
        """Verify that private_data is injected per recipient."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()

        email_context = {"client_name": "Corp", "plan_name": "Pro"}

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            result = EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context=email_context,
                recipient_user_ids=["user-1"],
            )

        # Verify emailing was created with enriched context
        call_args = emailing_service.entity_class.call_args
        created_context = call_args.kwargs["context"]
        assert created_context["private_data"]["first_name"] == "Alice"
        assert created_context["private_data"]["last_name"] == "Smith"
        assert created_context["client_name"] == "Corp"
        assert created_context["plan_name"] == "Pro"

    def test_original_context_not_mutated(self):
        """Verify that the original email_context dict is not mutated."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()

        email_context = {"client_name": "Corp"}

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context=email_context,
                recipient_user_ids=["user-1"],
            )

        # Original dict should not have private_data
        assert "private_data" not in email_context

    def test_no_private_data_when_absent(self):
        """Verify no private_data when user has no private_data."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()
        user.private_data = None

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={"key": "value"},
                recipient_user_ids=["user-1"],
            )

        call_args = emailing_service.entity_class.call_args
        created_context = call_args.kwargs["context"]
        assert "private_data" not in created_context

    def test_should_send_fn_filters_recipients(self):
        """Verify should_send_fn filters out recipients."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()

        # Filter out all recipients
        should_send_fn = Mock(return_value=False)

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            result = EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={},
                recipient_user_ids=["user-1"],
                should_send_fn=should_send_fn,
            )

        assert result == []
        should_send_fn.assert_called_once_with("user-1")

    def test_skips_user_without_email(self):
        """Verify users without email are skipped."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()
        user.email_address = None

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            result = EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={},
                recipient_user_ids=["user-1"],
            )

        assert result == []

    def test_skips_nonexistent_user(self):
        """Verify nonexistent users are skipped."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()
        session.get.return_value = None

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            result = EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={},
                recipient_user_ids=["user-1"],
            )

        assert result == []

    def test_emailing_created_per_recipient(self):
        """Verify emailing record is created for each valid recipient."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            result = EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={},
                recipient_user_ids=["user-1"],
            )

        emailing_service.entity_class.assert_called_once()
        session.add.assert_called_once()
        assert len(result) == 1

    def test_none_email_context_treated_as_empty_dict(self):
        """Verify None email_context is handled gracefully."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            result = EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context=None,
                recipient_user_ids=["user-1"],
            )

        call_args = emailing_service.entity_class.call_args
        created_context = call_args.kwargs["context"]
        # Should still have private_data even with None email_context
        assert created_context["private_data"]["first_name"] == "Alice"

    def test_user_language_used_for_emailing(self):
        """Verify user's language is used for the emailing record."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()
        user.language_id = "fr"

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={},
                recipient_user_ids=["user-1"],
            )

        call_args = emailing_service.entity_class.call_args
        assert call_args.kwargs["language_id"] == "fr"

    def test_default_language_when_user_has_none(self):
        """Verify default language 'fr' when user has no language."""
        app_manager, session, user, emailing_service, emailing_instance = self._setup_mocks()
        user.language_id = None

        with patch.object(EmailingBatchService, "app_manager", app_manager):
            EmailingBatchService._create_emails_sync(
                session=session,
                type_id="TEST_TYPE",
                email_context={},
                recipient_user_ids=["user-1"],
            )

        call_args = emailing_service.entity_class.call_args
        assert call_args.kwargs["language_id"] == "fr"
