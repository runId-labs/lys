"""
Unit tests for user_auth access_level module fixtures.
"""
from lys.apps.user_auth.modules.access_level.fixtures import AccessLevelFixtures
from lys.core.fixtures import EntityFixtures


class TestAccessLevelFixtures:
    def test_exists(self):
        assert AccessLevelFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(AccessLevelFixtures, EntityFixtures)

    def test_has_data_list(self):
        assert AccessLevelFixtures.data_list is not None
        assert len(AccessLevelFixtures.data_list) == 2

    def test_has_model(self):
        assert AccessLevelFixtures.model is not None

    def test_delete_previous_data_is_false(self):
        assert AccessLevelFixtures.delete_previous_data is False

    def test_data_list_contains_connected(self):
        from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
        ids = [d["id"] for d in AccessLevelFixtures.data_list]
        assert CONNECTED_ACCESS_LEVEL in ids

    def test_data_list_contains_owner(self):
        from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
        ids = [d["id"] for d in AccessLevelFixtures.data_list]
        assert OWNER_ACCESS_LEVEL in ids
