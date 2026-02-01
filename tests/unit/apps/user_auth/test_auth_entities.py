"""
Unit tests for user_auth auth module entities.

Tests entity structure.
"""

import pytest


class TestLoginAttemptEntity:
    """Tests for LoginAttempt abstract entity."""

    def test_entity_exists(self):
        """Test LoginAttempt entity exists."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttempt
        assert LoginAttempt is not None

    def test_entity_inherits_from_entity(self):
        """Test LoginAttempt inherits from Entity."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttempt
        from lys.core.entities import Entity
        assert issubclass(LoginAttempt, Entity)

    def test_entity_is_abstract(self):
        """Test LoginAttempt is abstract."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttempt
        assert LoginAttempt.__abstract__ is True

    def test_entity_has_status_id_column(self):
        """Test LoginAttempt has status_id column."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttempt
        assert "status_id" in LoginAttempt.__annotations__

    def test_entity_has_attempt_count_column(self):
        """Test LoginAttempt has attempt_count column."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttempt
        assert "attempt_count" in LoginAttempt.__annotations__


class TestUserLoginAttemptEntity:
    """Tests for UserLoginAttempt entity."""

    def test_entity_exists(self):
        """Test UserLoginAttempt entity exists."""
        from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt
        assert UserLoginAttempt is not None

    def test_entity_inherits_from_login_attempt(self):
        """Test UserLoginAttempt inherits from LoginAttempt."""
        from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt, LoginAttempt
        assert issubclass(UserLoginAttempt, LoginAttempt)

    def test_entity_has_tablename(self):
        """Test UserLoginAttempt has __tablename__."""
        from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt
        assert UserLoginAttempt.__tablename__ == "user_login_attempt"

    def test_entity_has_user_id_column(self):
        """Test UserLoginAttempt has user_id column."""
        from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt
        assert "user_id" in UserLoginAttempt.__annotations__


class TestLoginAttemptStatusEntity:
    """Tests for LoginAttemptStatus entity."""

    def test_entity_exists(self):
        """Test LoginAttemptStatus entity exists."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttemptStatus
        assert LoginAttemptStatus is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test LoginAttemptStatus inherits from ParametricEntity."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttemptStatus
        from lys.core.entities import ParametricEntity
        assert issubclass(LoginAttemptStatus, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test LoginAttemptStatus has __tablename__."""
        from lys.apps.user_auth.modules.auth.entities import LoginAttemptStatus
        assert LoginAttemptStatus.__tablename__ == "login_attempt_status"
