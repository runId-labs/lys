"""
Unit tests for base access_level module entities.

Tests entity structure.
"""

import pytest


class TestAccessLevelEntity:
    """Tests for AccessLevel entity."""

    def test_entity_exists(self):
        """Test AccessLevel entity exists."""
        from lys.apps.base.modules.access_level.entities import AccessLevel
        assert AccessLevel is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test AccessLevel inherits from ParametricEntity."""
        from lys.apps.base.modules.access_level.entities import AccessLevel
        from lys.core.entities import ParametricEntity
        assert issubclass(AccessLevel, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test AccessLevel has correct __tablename__."""
        from lys.apps.base.modules.access_level.entities import AccessLevel
        from lys.core.consts.tablenames import ACCESS_LEVEL_TABLENAME
        assert AccessLevel.__tablename__ == ACCESS_LEVEL_TABLENAME
