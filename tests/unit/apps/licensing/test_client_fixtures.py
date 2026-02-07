"""
Unit tests for licensing client fixtures.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestClientDevFixtures:
    """Tests for ClientDevFixtures."""

    def test_fixture_class_exists(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        assert ClientDevFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(ClientDevFixtures, EntityFixtures)

    def test_data_list_exists(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        assert hasattr(ClientDevFixtures, "data_list")
        assert isinstance(ClientDevFixtures.data_list, list)

    def test_data_list_has_clients(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        assert len(ClientDevFixtures.data_list) >= 3

    def test_all_entries_have_attributes(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        for entry in ClientDevFixtures.data_list:
            assert "attributes" in entry

    def test_all_entries_have_name(self):
        from lys.apps.licensing.modules.client.fixtures import ClientDevFixtures
        for entry in ClientDevFixtures.data_list:
            assert "name" in entry["attributes"]
            assert isinstance(entry["attributes"]["name"], str)
