"""
Unit tests for base one_time_token module entities.

Tests entity structure.
"""

import pytest


class TestOneTimeTokenStatusEntity:
    """Tests for OneTimeTokenStatus entity."""

    def test_entity_exists(self):
        """Test OneTimeTokenStatus entity exists."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenStatus
        assert OneTimeTokenStatus is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test OneTimeTokenStatus inherits from ParametricEntity."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenStatus
        from lys.core.entities import ParametricEntity
        assert issubclass(OneTimeTokenStatus, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test OneTimeTokenStatus has correct __tablename__."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenStatus
        assert OneTimeTokenStatus.__tablename__ == "one_time_token_status"


class TestOneTimeTokenTypeEntity:
    """Tests for OneTimeTokenType entity."""

    def test_entity_exists(self):
        """Test OneTimeTokenType entity exists."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenType
        assert OneTimeTokenType is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test OneTimeTokenType inherits from ParametricEntity."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenType
        from lys.core.entities import ParametricEntity
        assert issubclass(OneTimeTokenType, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test OneTimeTokenType has correct __tablename__."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenType
        assert OneTimeTokenType.__tablename__ == "one_time_token_type"

    def test_entity_has_duration_column(self):
        """Test OneTimeTokenType has duration column."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeTokenType
        assert "duration" in OneTimeTokenType.__annotations__


class TestOneTimeTokenEntity:
    """Tests for OneTimeToken abstract entity."""

    def test_entity_exists(self):
        """Test OneTimeToken entity exists."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert OneTimeToken is not None

    def test_entity_inherits_from_entity(self):
        """Test OneTimeToken inherits from Entity."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        from lys.core.entities import Entity
        assert issubclass(OneTimeToken, Entity)

    def test_entity_is_abstract(self):
        """Test OneTimeToken is abstract."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert OneTimeToken.__abstract__ is True

    def test_entity_has_used_at_column(self):
        """Test OneTimeToken has used_at column."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert "used_at" in OneTimeToken.__annotations__

    def test_entity_has_status_id_column(self):
        """Test OneTimeToken has status_id column."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert "status_id" in OneTimeToken.__annotations__

    def test_entity_has_type_id_column(self):
        """Test OneTimeToken has type_id column."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert "type_id" in OneTimeToken.__annotations__

    def test_entity_has_expires_at_property(self):
        """Test OneTimeToken has expires_at property."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert hasattr(OneTimeToken, "expires_at")

    def test_entity_has_is_expired_property(self):
        """Test OneTimeToken has is_expired property."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert hasattr(OneTimeToken, "is_expired")

    def test_entity_has_is_used_property(self):
        """Test OneTimeToken has is_used property."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert hasattr(OneTimeToken, "is_used")

    def test_entity_has_is_valid_property(self):
        """Test OneTimeToken has is_valid property."""
        from lys.apps.base.modules.one_time_token.entities import OneTimeToken
        assert hasattr(OneTimeToken, "is_valid")
