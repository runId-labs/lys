"""
Unit tests for user_auth auth module fixtures.
"""
from lys.apps.user_auth.modules.auth.fixtures import LoginAttemptStatusFixtures
from lys.core.fixtures import EntityFixtures


class TestLoginAttemptStatusFixtures:
    def test_exists(self):
        assert LoginAttemptStatusFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(LoginAttemptStatusFixtures, EntityFixtures)

    def test_has_data_list(self):
        assert LoginAttemptStatusFixtures.data_list is not None
        assert len(LoginAttemptStatusFixtures.data_list) == 2

    def test_has_model(self):
        assert LoginAttemptStatusFixtures.model is not None
