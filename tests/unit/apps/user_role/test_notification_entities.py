"""
Unit tests for user_role notification entities.

Validates that the user_role override of NotificationType still inherits the
columns added on the base class (e.g. severity_id), so the override pattern
does not silently drop them.
"""
import inspect as python_inspect

from sqlalchemy.orm.properties import MappedColumn


def _get_mapped_column(cls, name):
    attr = python_inspect.getattr_static(cls, name)
    assert isinstance(attr, MappedColumn), f"{name} is not a MappedColumn"
    return attr.column


class TestUserRoleNotificationTypeOverride:
    def test_class_exists(self):
        from lys.apps.user_role.modules.notification.entities import NotificationType
        assert NotificationType is not None

    def test_inherits_from_base_notification_type(self):
        from lys.apps.user_auth.modules.notification.entities import (
            NotificationType as BaseNotificationType,
        )
        from lys.apps.user_role.modules.notification.entities import NotificationType
        assert issubclass(NotificationType, BaseNotificationType)

    def test_tablename_is_shared_with_base(self):
        from lys.apps.user_role.modules.notification.entities import NotificationType
        assert NotificationType.__tablename__ == "notification_type"

    def test_severity_id_inherited_from_base(self):
        from lys.apps.user_role.modules.notification.entities import NotificationType
        # Inherited mapped column — must remain accessible on the override.
        _get_mapped_column(NotificationType, "severity_id")

    def test_has_roles_relationship(self):
        from lys.apps.user_role.modules.notification.entities import NotificationType
        assert hasattr(NotificationType, "roles")


class TestNotificationTypeRoleAssociationTable:
    def test_table_exists(self):
        from lys.apps.user_role.modules.notification.entities import notification_type_role
        assert notification_type_role is not None
        assert notification_type_role.name == "notification_type_role"

    def test_columns_are_primary_keys(self):
        from lys.apps.user_role.modules.notification.entities import notification_type_role
        pk_cols = {c.name for c in notification_type_role.primary_key.columns}
        assert pk_cols == {"notification_type_id", "role_id"}

    def test_fk_cascades(self):
        from lys.apps.user_role.modules.notification.entities import notification_type_role
        for col in notification_type_role.columns:
            for fk in col.foreign_keys:
                assert fk.ondelete == "CASCADE"
