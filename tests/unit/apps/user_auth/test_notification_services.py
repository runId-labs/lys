"""
Unit tests for user_auth notification services structure.
"""
import inspect


class TestNotificationBatchServiceStructure:
    """Tests for NotificationBatchService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.notification.services import NotificationBatchService
        assert NotificationBatchService is not None

    def test_has_dispatch_method(self):
        from lys.apps.user_auth.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "dispatch")
        assert inspect.iscoroutinefunction(NotificationBatchService.dispatch)

    def test_has_dispatch_sync_method(self):
        from lys.apps.user_auth.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "dispatch_sync")
        assert not inspect.iscoroutinefunction(NotificationBatchService.dispatch_sync)

    def test_has_resolve_recipients_method(self):
        from lys.apps.user_auth.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "_resolve_recipients")

    def test_has_create_notifications_and_publish_method(self):
        from lys.apps.user_auth.modules.notification.services import NotificationBatchService
        assert hasattr(NotificationBatchService, "_create_notifications_and_publish")


class TestNotificationServiceStructure:
    """Tests for NotificationService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.notification.services import NotificationService
        assert NotificationService is not None

    def test_has_count_unread_method(self):
        from lys.apps.user_auth.modules.notification.services import NotificationService
        assert hasattr(NotificationService, "count_unread")
        assert inspect.iscoroutinefunction(NotificationService.count_unread)


class TestNotificationTypeServiceStructure:
    """Tests for NotificationTypeService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.notification.services import NotificationTypeService
        assert NotificationTypeService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.user_auth.modules.notification.services import NotificationTypeService
        from lys.core.services import EntityService
        assert issubclass(NotificationTypeService, EntityService)
