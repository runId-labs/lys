"""
Unit tests for user_auth notification module entities.

Tests entity structure, MappedColumn attributes, methods, and method types.
"""
import inspect as python_inspect

from sqlalchemy.orm.properties import MappedColumn


def _get_mapped_column(cls, name):
    """Retrieve a MappedColumn attribute from a class without triggering descriptors."""
    attr = python_inspect.getattr_static(cls, name)
    assert isinstance(attr, MappedColumn), f"{name} is not a MappedColumn"
    return attr.column


class TestNotificationTypeEntity:
    """Tests for NotificationType entity."""

    def test_entity_exists(self):
        """Test NotificationType entity exists."""
        from lys.apps.user_auth.modules.notification.entities import NotificationType
        assert NotificationType is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test NotificationType inherits from ParametricEntity."""
        from lys.apps.user_auth.modules.notification.entities import NotificationType
        from lys.core.entities import ParametricEntity
        assert issubclass(NotificationType, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test NotificationType has correct __tablename__."""
        from lys.apps.user_auth.modules.notification.entities import NotificationType
        assert NotificationType.__tablename__ == "notification_type"


class TestNotificationBatchEntity:
    """Tests for NotificationBatch entity."""

    def test_entity_exists(self):
        """Test NotificationBatch entity exists."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        assert NotificationBatch is not None

    def test_entity_inherits_from_entity(self):
        """Test NotificationBatch inherits from Entity."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        from lys.core.entities import Entity
        assert issubclass(NotificationBatch, Entity)

    def test_entity_has_tablename(self):
        """Test NotificationBatch has correct __tablename__."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        assert NotificationBatch.__tablename__ == "notification_batch"

    def test_type_id_is_mapped_column(self):
        """Test type_id is a MappedColumn on NotificationBatch."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        _get_mapped_column(NotificationBatch, "type_id")

    def test_triggered_by_user_id_is_mapped_column(self):
        """Test triggered_by_user_id is a MappedColumn on NotificationBatch."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        _get_mapped_column(NotificationBatch, "triggered_by_user_id")

    def test_data_is_mapped_column(self):
        """Test data is a MappedColumn on NotificationBatch."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        _get_mapped_column(NotificationBatch, "data")

    def test_has_accessing_users_method(self):
        """Test NotificationBatch has accessing_users method."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        assert hasattr(NotificationBatch, "accessing_users")
        assert callable(getattr(NotificationBatch, "accessing_users"))

    def test_has_accessing_organizations_method(self):
        """Test NotificationBatch has accessing_organizations method."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        assert hasattr(NotificationBatch, "accessing_organizations")
        assert callable(getattr(NotificationBatch, "accessing_organizations"))

    def test_accessing_organizations_returns_empty_dict(self):
        """Test NotificationBatch.accessing_organizations returns empty dict."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        batch = NotificationBatch.__new__(NotificationBatch)
        assert batch.accessing_organizations() == {}

    def test_accessing_users_returns_triggered_user(self):
        """Test NotificationBatch.accessing_users returns triggered_by_user_id."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        batch = NotificationBatch.__new__(NotificationBatch)
        batch.triggered_by_user_id = "user-123"
        assert batch.accessing_users() == ["user-123"]

    def test_accessing_users_returns_empty_when_no_trigger_user(self):
        """Test NotificationBatch.accessing_users returns empty list when no triggered_by_user_id."""
        from lys.apps.user_auth.modules.notification.entities import NotificationBatch
        batch = NotificationBatch.__new__(NotificationBatch)
        batch.triggered_by_user_id = None
        assert batch.accessing_users() == []


class TestNotificationEntity:
    """Tests for Notification entity."""

    def test_entity_exists(self):
        """Test Notification entity exists."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        assert Notification is not None

    def test_entity_inherits_from_entity(self):
        """Test Notification inherits from Entity."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        from lys.core.entities import Entity
        assert issubclass(Notification, Entity)

    def test_entity_has_tablename(self):
        """Test Notification has correct __tablename__."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        assert Notification.__tablename__ == "notification"

    def test_batch_id_is_mapped_column(self):
        """Test batch_id is a MappedColumn on Notification."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        _get_mapped_column(Notification, "batch_id")

    def test_user_id_is_mapped_column(self):
        """Test user_id is a MappedColumn on Notification."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        _get_mapped_column(Notification, "user_id")

    def test_is_read_is_mapped_column(self):
        """Test is_read is a MappedColumn on Notification."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        _get_mapped_column(Notification, "is_read")

    def test_has_accessing_users_method(self):
        """Test Notification has accessing_users method."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        assert hasattr(Notification, "accessing_users")
        assert callable(getattr(Notification, "accessing_users"))

    def test_has_accessing_organizations_method(self):
        """Test Notification has accessing_organizations method."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        assert hasattr(Notification, "accessing_organizations")
        assert callable(getattr(Notification, "accessing_organizations"))

    def test_accessing_users_returns_user_id(self):
        """Test Notification.accessing_users returns user_id."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        notif = Notification.__new__(Notification)
        notif.user_id = "user-456"
        assert notif.accessing_users() == ["user-456"]

    def test_accessing_organizations_returns_empty_dict(self):
        """Test Notification.accessing_organizations returns empty dict."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        notif = Notification.__new__(Notification)
        assert notif.accessing_organizations() == {}

    def test_user_accessing_filters_is_classmethod(self):
        """Test user_accessing_filters is a classmethod on Notification."""
        from lys.apps.user_auth.modules.notification.entities import Notification
        attr = python_inspect.getattr_static(Notification, "user_accessing_filters")
        assert isinstance(attr, classmethod), "user_accessing_filters should be a classmethod"

    def test_user_accessing_filters_returns_stmt_and_filters(self):
        """Test user_accessing_filters returns stmt and list of filters."""
        from unittest.mock import MagicMock
        from lys.apps.user_auth.modules.notification.entities import Notification
        stmt = MagicMock()
        result_stmt, filters = Notification.user_accessing_filters(stmt, "user-789")
        assert result_stmt is stmt
        assert len(filters) == 1
