"""
Unit tests for user_auth notification module nodes.
"""
from lys.apps.user_auth.modules.notification.nodes import (
    NotificationBatchNode,
    NotificationNode,
    UnreadNotificationsCountNode,
    MarkNotificationsReadNode,
)


class TestNotificationBatchNode:
    def test_exists(self):
        assert NotificationBatchNode is not None

    def test_has_id_field(self):
        assert "id" in NotificationBatchNode.__annotations__

    def test_has_type_id_field(self):
        assert "type_id" in NotificationBatchNode.__annotations__

    def test_has_data_field(self):
        assert "data" in NotificationBatchNode.__annotations__

    def test_has_created_at_field(self):
        assert "created_at" in NotificationBatchNode.__annotations__


class TestNotificationNode:
    def test_exists(self):
        assert NotificationNode is not None

    def test_has_id_field(self):
        assert "id" in NotificationNode.__annotations__

    def test_has_user_id_field(self):
        assert "user_id" in NotificationNode.__annotations__

    def test_has_is_read_field(self):
        assert "is_read" in NotificationNode.__annotations__

    def test_has_batch_method(self):
        assert hasattr(NotificationNode, "batch")


class TestUnreadNotificationsCountNode:
    def test_exists(self):
        assert UnreadNotificationsCountNode is not None

    def test_has_unread_count_field(self):
        assert "unread_count" in UnreadNotificationsCountNode.__annotations__


class TestMarkNotificationsReadNode:
    def test_exists(self):
        assert MarkNotificationsReadNode is not None

    def test_has_unread_count_field(self):
        assert "unread_count" in MarkNotificationsReadNode.__annotations__
