"""
Unit tests for base language module entities.

Tests entity structure.
"""

import pytest


class TestLanguageEntity:
    """Tests for Language entity."""

    def test_entity_exists(self):
        """Test Language entity exists."""
        from lys.apps.base.modules.language.entities import Language
        assert Language is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test Language inherits from ParametricEntity."""
        from lys.apps.base.modules.language.entities import Language
        from lys.core.entities import ParametricEntity
        assert issubclass(Language, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test Language has correct __tablename__."""
        from lys.apps.base.modules.language.entities import Language
        assert Language.__tablename__ == "language"
