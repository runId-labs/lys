"""
Unit tests for base access_level module fixtures.

Tests fixtures configuration and data.
"""

import pytest


class TestAccessLevelFixtures:
    """Tests for AccessLevelFixtures."""

    def test_fixture_exists(self):
        """Test AccessLevelFixtures class exists."""
        from lys.apps.base.modules.access_level.fixtures import AccessLevelFixtures
        assert AccessLevelFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test AccessLevelFixtures inherits from EntityFixtures."""
        from lys.apps.base.modules.access_level.fixtures import AccessLevelFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(AccessLevelFixtures, EntityFixtures)

    def test_fixture_has_model(self):
        """Test AccessLevelFixtures has model attribute."""
        from lys.apps.base.modules.access_level.fixtures import AccessLevelFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert AccessLevelFixtures.model == ParametricEntityFixturesModel

    def test_fixture_has_data_list(self):
        """Test AccessLevelFixtures has data_list attribute."""
        from lys.apps.base.modules.access_level.fixtures import AccessLevelFixtures
        assert hasattr(AccessLevelFixtures, "data_list")
        assert isinstance(AccessLevelFixtures.data_list, list)

    def test_data_list_contains_internal_service(self):
        """Test data_list contains INTERNAL_SERVICE access level."""
        from lys.apps.base.modules.access_level.fixtures import AccessLevelFixtures
        from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL

        ids = [item["id"] for item in AccessLevelFixtures.data_list]
        assert INTERNAL_SERVICE_ACCESS_LEVEL in ids

    def test_data_list_items_have_required_fields(self):
        """Test each data_list item has id and attributes."""
        from lys.apps.base.modules.access_level.fixtures import AccessLevelFixtures

        for item in AccessLevelFixtures.data_list:
            assert "id" in item
            assert "attributes" in item
            assert "enabled" in item["attributes"]
