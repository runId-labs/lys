"""
Unit tests for base language module fixtures.

Tests fixtures configuration and data.
"""

import pytest


class TestLanguageFixtures:
    """Tests for LanguageFixtures."""

    def test_fixture_exists(self):
        """Test LanguageFixtures class exists."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures
        assert LanguageFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test LanguageFixtures inherits from EntityFixtures."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(LanguageFixtures, EntityFixtures)

    def test_fixture_has_model(self):
        """Test LanguageFixtures has model attribute."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert LanguageFixtures.model == ParametricEntityFixturesModel

    def test_fixture_has_data_list(self):
        """Test LanguageFixtures has data_list attribute."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures
        assert hasattr(LanguageFixtures, "data_list")
        assert isinstance(LanguageFixtures.data_list, list)

    def test_data_list_contains_french_language(self):
        """Test data_list contains French language."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures
        from lys.apps.base.modules.language.consts import FRENCH_LANGUAGE

        ids = [item["id"] for item in LanguageFixtures.data_list]
        assert FRENCH_LANGUAGE in ids

    def test_data_list_contains_english_language(self):
        """Test data_list contains English language."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures
        from lys.apps.base.modules.language.consts import ENGLISH_LANGUAGE

        ids = [item["id"] for item in LanguageFixtures.data_list]
        assert ENGLISH_LANGUAGE in ids

    def test_data_list_items_have_required_fields(self):
        """Test each data_list item has id and attributes."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures

        for item in LanguageFixtures.data_list:
            assert "id" in item
            assert "attributes" in item
            assert "enabled" in item["attributes"]

    def test_all_languages_are_enabled(self):
        """Test all languages in fixtures are enabled."""
        from lys.apps.base.modules.language.fixtures import LanguageFixtures

        for item in LanguageFixtures.data_list:
            assert item["attributes"]["enabled"] is True
