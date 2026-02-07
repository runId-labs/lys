"""
Unit tests for organization notification services structure.
"""
import inspect


class TestOrganizationNotificationBatchServiceStructure:
    """Tests for organization NotificationBatchService class structure."""

    def test_service_exists(self):
        from lys.apps.organization.modules.notification.services import NotificationBatchService
        assert NotificationBatchService is not None

    def test_inherits_from_base_notification_batch_service(self):
        from lys.apps.organization.modules.notification.services import NotificationBatchService
        from lys.apps.user_auth.modules.notification.services import (
            NotificationBatchService as BaseNotificationBatchService,
        )
        assert issubclass(NotificationBatchService, BaseNotificationBatchService)

    def test_has_dispatch_method(self):
        from lys.apps.organization.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "dispatch")
        assert inspect.iscoroutinefunction(NotificationBatchService.dispatch)

    def test_has_dispatch_sync_method(self):
        from lys.apps.organization.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "dispatch_sync")

    def test_has_resolve_recipients_method(self):
        from lys.apps.organization.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "_resolve_recipients")


class TestOrganizationDataModel:
    """Tests for OrganizationData Pydantic model."""

    def test_model_exists(self):
        from lys.apps.organization.modules.notification.services import OrganizationData
        assert OrganizationData is not None

    def test_model_accepts_client_ids(self):
        from lys.apps.organization.modules.notification.services import OrganizationData
        data = OrganizationData(client_ids=["client-1", "client-2"])
        assert data.client_ids == ["client-1", "client-2"]

    def test_model_accepts_empty(self):
        from lys.apps.organization.modules.notification.services import OrganizationData
        data = OrganizationData()
        assert data is not None
