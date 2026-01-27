"""
Unit tests for user_auth user module entities.

Tests entity structure and relationships.
"""

import pytest


class TestUserStatusEntity:
    """Tests for UserStatus entity."""

    def test_entity_exists(self):
        """Test UserStatus entity exists."""
        from lys.apps.user_auth.modules.user.entities import UserStatus
        assert UserStatus is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test UserStatus inherits from ParametricEntity."""
        from lys.apps.user_auth.modules.user.entities import UserStatus
        from lys.core.entities import ParametricEntity
        assert issubclass(UserStatus, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test UserStatus has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import UserStatus
        assert UserStatus.__tablename__ == "user_status"


class TestGenderEntity:
    """Tests for Gender entity."""

    def test_entity_exists(self):
        """Test Gender entity exists."""
        from lys.apps.user_auth.modules.user.entities import Gender
        assert Gender is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test Gender inherits from ParametricEntity."""
        from lys.apps.user_auth.modules.user.entities import Gender
        from lys.core.entities import ParametricEntity
        assert issubclass(Gender, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test Gender has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import Gender
        assert Gender.__tablename__ == "gender"


class TestUserAuditLogTypeEntity:
    """Tests for UserAuditLogType entity."""

    def test_entity_exists(self):
        """Test UserAuditLogType entity exists."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLogType
        assert UserAuditLogType is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test UserAuditLogType inherits from ParametricEntity."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLogType
        from lys.core.entities import ParametricEntity
        assert issubclass(UserAuditLogType, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test UserAuditLogType has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLogType
        assert UserAuditLogType.__tablename__ == "user_audit_log_type"


class TestUserEmailAddressEntity:
    """Tests for UserEmailAddress entity."""

    def test_entity_exists(self):
        """Test UserEmailAddress entity exists."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert UserEmailAddress is not None

    def test_entity_inherits_from_abstract_email_address(self):
        """Test UserEmailAddress inherits from AbstractEmailAddress."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        from lys.core.abstracts.email_address import AbstractEmailAddress
        assert issubclass(UserEmailAddress, AbstractEmailAddress)

    def test_entity_has_tablename(self):
        """Test UserEmailAddress has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert UserEmailAddress.__tablename__ == "user_email_address"

    def test_entity_has_user_id_column(self):
        """Test UserEmailAddress has user_id column."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert "user_id" in UserEmailAddress.__annotations__

    def test_entity_has_accessing_users_method(self):
        """Test UserEmailAddress has accessing_users method."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert hasattr(UserEmailAddress, "accessing_users")

    def test_entity_has_accessing_organizations_method(self):
        """Test UserEmailAddress has accessing_organizations method."""
        from lys.apps.user_auth.modules.user.entities import UserEmailAddress
        assert hasattr(UserEmailAddress, "accessing_organizations")


class TestUserEntity:
    """Tests for User entity."""

    def test_entity_exists(self):
        """Test User entity exists."""
        from lys.apps.user_auth.modules.user.entities import User
        assert User is not None

    def test_entity_inherits_from_entity(self):
        """Test User inherits from Entity."""
        from lys.apps.user_auth.modules.user.entities import User
        from lys.core.entities import Entity
        assert issubclass(User, Entity)

    def test_entity_has_tablename(self):
        """Test User has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import User
        assert User.__tablename__ == "user"

    def test_entity_has_password_column(self):
        """Test User has password column."""
        from lys.apps.user_auth.modules.user.entities import User
        assert "password" in User.__annotations__

    def test_entity_has_is_super_user_column(self):
        """Test User has is_super_user column."""
        from lys.apps.user_auth.modules.user.entities import User
        assert "is_super_user" in User.__annotations__

    def test_entity_has_status_id_column(self):
        """Test User has status_id column."""
        from lys.apps.user_auth.modules.user.entities import User
        assert "status_id" in User.__annotations__

    def test_entity_has_language_id_column(self):
        """Test User has language_id column."""
        from lys.apps.user_auth.modules.user.entities import User
        assert "language_id" in User.__annotations__

    def test_entity_has_email_address_relationship(self):
        """Test User has email_address relationship."""
        from lys.apps.user_auth.modules.user.entities import User
        assert hasattr(User, "email_address")


class TestUserPrivateDataEntity:
    """Tests for UserPrivateData entity."""

    def test_entity_exists(self):
        """Test UserPrivateData entity exists."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        assert UserPrivateData is not None

    def test_entity_inherits_from_entity(self):
        """Test UserPrivateData inherits from Entity."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        from lys.core.entities import Entity
        assert issubclass(UserPrivateData, Entity)

    def test_entity_has_tablename(self):
        """Test UserPrivateData has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import UserPrivateData
        assert UserPrivateData.__tablename__ == "user_private_data"


class TestUserAuditLogEntity:
    """Tests for UserAuditLog entity."""

    def test_entity_exists(self):
        """Test UserAuditLog entity exists."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        assert UserAuditLog is not None

    def test_entity_inherits_from_entity(self):
        """Test UserAuditLog inherits from Entity."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        from lys.core.entities import Entity
        assert issubclass(UserAuditLog, Entity)

    def test_entity_has_tablename(self):
        """Test UserAuditLog has __tablename__."""
        from lys.apps.user_auth.modules.user.entities import UserAuditLog
        assert UserAuditLog.__tablename__ == "user_audit_log"
