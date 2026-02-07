"""
Unit tests for user_auth user module entities with column-level detail.

Tests entity MappedColumn structure, method existence, and method types
using inspect.getattr_static to avoid triggering SQLAlchemy descriptor logic.
"""
import inspect as python_inspect

import pytest

from sqlalchemy.orm.properties import MappedColumn


def _get_mapped_column(cls, name):
    """Retrieve a MappedColumn attribute from a class without triggering descriptors."""
    attr = python_inspect.getattr_static(cls, name)
    assert isinstance(attr, MappedColumn), f"{name} is not a MappedColumn"
    return attr.column


class TestUserEmailAddressMappedColumns:
    """Tests for UserEmailAddress entity MappedColumn attributes and methods."""

    def test_user_id_is_mapped_column(self):
        """Test user_id is a MappedColumn on UserEmailAddress."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        _get_mapped_column(UserEmailAddress, "user_id")

    def test_has_accessing_users_method(self):
        """Test UserEmailAddress has accessing_users method."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert hasattr(UserEmailAddress, "accessing_users")
        assert callable(getattr(UserEmailAddress, "accessing_users"))

    def test_has_accessing_organizations_method(self):
        """Test UserEmailAddress has accessing_organizations method."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert hasattr(UserEmailAddress, "accessing_organizations")
        assert callable(getattr(UserEmailAddress, "accessing_organizations"))


class TestUserMappedColumns:
    """Tests for User entity MappedColumn attributes, methods, and special descriptors."""

    def test_password_is_mapped_column(self):
        """Test password is a MappedColumn on User."""
        from lys.apps.user_auth.modules.user.entities import User
        _get_mapped_column(User, "password")

    def test_is_super_user_is_mapped_column(self):
        """Test is_super_user is a MappedColumn on User."""
        from lys.apps.user_auth.modules.user.entities import User
        _get_mapped_column(User, "is_super_user")

    def test_status_id_is_mapped_column(self):
        """Test status_id is a MappedColumn on User."""
        from lys.apps.user_auth.modules.user.entities import User
        _get_mapped_column(User, "status_id")

    def test_language_id_is_mapped_column(self):
        """Test language_id is a MappedColumn on User."""
        from lys.apps.user_auth.modules.user.entities import User
        _get_mapped_column(User, "language_id")

    def test_login_name_is_staticmethod(self):
        """Test login_name is a staticmethod on User."""
        from lys.apps.user_auth.modules.user.entities import User
        attr = python_inspect.getattr_static(User, "login_name")
        assert isinstance(attr, staticmethod), "login_name should be a staticmethod"

    def test_has_accessing_users_method(self):
        """Test User has accessing_users method."""
        from lys.apps.user_auth.modules.user.entities import User
        assert hasattr(User, "accessing_users")
        assert callable(getattr(User, "accessing_users"))

    def test_has_accessing_organizations_method(self):
        """Test User has accessing_organizations method."""
        from lys.apps.user_auth.modules.user.entities import User
        assert hasattr(User, "accessing_organizations")
        assert callable(getattr(User, "accessing_organizations"))

    def test_user_accessing_filters_is_classmethod(self):
        """Test user_accessing_filters is a classmethod on User."""
        from lys.apps.user_auth.modules.user.entities import User
        attr = python_inspect.getattr_static(User, "user_accessing_filters")
        assert isinstance(attr, classmethod), "user_accessing_filters should be a classmethod"


class TestUserPrivateDataMappedColumns:
    """Tests for UserPrivateData entity MappedColumn attributes."""

    def test_user_id_is_mapped_column(self):
        """Test user_id is a MappedColumn on UserPrivateData."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        _get_mapped_column(UserPrivateData, "user_id")

    def test_first_name_is_mapped_column(self):
        """Test first_name is a MappedColumn on UserPrivateData."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        _get_mapped_column(UserPrivateData, "first_name")

    def test_last_name_is_mapped_column(self):
        """Test last_name is a MappedColumn on UserPrivateData."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        _get_mapped_column(UserPrivateData, "last_name")

    def test_gender_id_is_mapped_column(self):
        """Test gender_id is a MappedColumn on UserPrivateData."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        _get_mapped_column(UserPrivateData, "gender_id")

    def test_anonymized_at_is_mapped_column(self):
        """Test anonymized_at is a MappedColumn on UserPrivateData."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        _get_mapped_column(UserPrivateData, "anonymized_at")


class TestUserRefreshTokenMappedColumns:
    """Tests for UserRefreshToken entity MappedColumn attributes."""

    def test_once_expire_at_is_mapped_column(self):
        """Test once_expire_at is a MappedColumn on UserRefreshToken."""
        from lys.apps.user_auth.modules.user.entities import UserRefreshToken
        _get_mapped_column(UserRefreshToken, "once_expire_at")

    def test_connection_expire_at_is_mapped_column(self):
        """Test connection_expire_at is a MappedColumn on UserRefreshToken."""
        from lys.apps.user_auth.modules.user.entities import UserRefreshToken
        _get_mapped_column(UserRefreshToken, "connection_expire_at")

    def test_revoked_at_is_mapped_column(self):
        """Test revoked_at is a MappedColumn on UserRefreshToken."""
        from lys.apps.user_auth.modules.user.entities import UserRefreshToken
        _get_mapped_column(UserRefreshToken, "revoked_at")

    def test_used_at_is_mapped_column(self):
        """Test used_at is a MappedColumn on UserRefreshToken."""
        from lys.apps.user_auth.modules.user.entities import UserRefreshToken
        _get_mapped_column(UserRefreshToken, "used_at")

    def test_user_id_is_mapped_column(self):
        """Test user_id is a MappedColumn on UserRefreshToken."""
        from lys.apps.user_auth.modules.user.entities import UserRefreshToken
        _get_mapped_column(UserRefreshToken, "user_id")


class TestUserEmailingMappedColumns:
    """Tests for UserEmailing entity MappedColumn attributes."""

    def test_user_id_is_mapped_column(self):
        """Test user_id is a MappedColumn on UserEmailing."""
        from lys.apps.user_auth.modules.user.entities import UserEmailing
        _get_mapped_column(UserEmailing, "user_id")

    def test_emailing_id_is_mapped_column(self):
        """Test emailing_id is a MappedColumn on UserEmailing."""
        from lys.apps.user_auth.modules.user.entities import UserEmailing
        _get_mapped_column(UserEmailing, "emailing_id")


class TestUserOneTimeTokenMappedColumns:
    """Tests for UserOneTimeToken entity MappedColumn attributes."""

    def test_user_id_is_mapped_column(self):
        """Test user_id is a MappedColumn on UserOneTimeToken."""
        from lys.apps.user_auth.modules.user.entities import UserOneTimeToken
        _get_mapped_column(UserOneTimeToken, "user_id")


class TestUserAuditLogMappedColumns:
    """Tests for UserAuditLog entity MappedColumn attributes."""

    def test_target_user_id_is_mapped_column(self):
        """Test target_user_id is a MappedColumn on UserAuditLog."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        _get_mapped_column(UserAuditLog, "target_user_id")

    def test_author_user_id_is_mapped_column(self):
        """Test author_user_id is a MappedColumn on UserAuditLog."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        _get_mapped_column(UserAuditLog, "author_user_id")

    def test_log_type_id_is_mapped_column(self):
        """Test log_type_id is a MappedColumn on UserAuditLog."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        _get_mapped_column(UserAuditLog, "log_type_id")

    def test_message_is_mapped_column(self):
        """Test message is a MappedColumn on UserAuditLog."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        _get_mapped_column(UserAuditLog, "message")

    def test_deleted_at_is_mapped_column(self):
        """Test deleted_at is a MappedColumn on UserAuditLog."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        _get_mapped_column(UserAuditLog, "deleted_at")
