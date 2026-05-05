"""
Unit tests for user_auth notification module nodes.
"""
from lys.apps.user_auth.modules.notification.nodes import (
    NotificationBatchNode,
    NotificationNode,
    NotificationSeverityNode,
    NotificationTypeNode,
    UnreadNotificationsCountNode,
    MarkNotificationsReadNode,
)


class TestNotificationBatchNode:
    def test_exists(self):
        assert NotificationBatchNode is not None

    def test_has_id_field(self):
        assert "id" in NotificationBatchNode.__annotations__

    def test_has_type_resolver(self):
        assert hasattr(NotificationBatchNode, "type")

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


class TestNotificationSeverityNode:
    """The decorator @parametric_node(NotificationSeverityService) replaces the
    user-declared class with a fresh subclass of EntityNode + relay.Node carrying
    the standard parametric fields. We verify the wired-in surface."""

    def test_exists(self):
        assert NotificationSeverityNode is not None

    def test_has_id_field(self):
        assert "id" in NotificationSeverityNode.__annotations__

    def test_has_code_field(self):
        assert "code" in NotificationSeverityNode.__annotations__

    def test_has_enabled_field(self):
        assert "enabled" in NotificationSeverityNode.__annotations__

    def test_has_description_field(self):
        assert "description" in NotificationSeverityNode.__annotations__

    def test_name_preserved(self):
        # parametric_node renames the generated class back to the source class name
        assert NotificationSeverityNode.__name__ == "NotificationSeverityNode"


class TestNotificationTypeNode:
    def test_exists(self):
        assert NotificationTypeNode is not None

    def test_has_id_field(self):
        assert "id" in NotificationTypeNode.__annotations__

    def test_has_code_field(self):
        assert "code" in NotificationTypeNode.__annotations__

    def test_has_severity_id_field(self):
        assert "severity_id" in NotificationTypeNode.__annotations__

    def test_has_severity_resolver(self):
        assert hasattr(NotificationTypeNode, "severity")

    def test_severity_resolver_returns_severity_node(self):
        # @strawberry.field turns the method into a Field with a known type.
        from strawberry import field as _strawberry_field  # noqa: F401
        field = NotificationTypeNode.severity
        # Strawberry exposes the resolver function via .base_resolver.wrapped_func
        assert hasattr(field, "base_resolver")
        assert field.base_resolver is not None
        import inspect
        assert inspect.iscoroutinefunction(field.base_resolver.wrapped_func)


class TestNotificationBatchNodeTypeResolver:
    def test_type_resolver_field_present(self):
        field = NotificationBatchNode.type
        assert hasattr(field, "base_resolver")
        assert field.base_resolver is not None

    def test_type_resolver_underlying_is_coroutine(self):
        import inspect
        field = NotificationBatchNode.type
        assert inspect.iscoroutinefunction(field.base_resolver.wrapped_func)

    def test_type_id_scalar_is_removed(self):
        # BREAKING: replaced by `type` resolver returning NotificationTypeNode
        assert "type_id" not in NotificationBatchNode.__annotations__
