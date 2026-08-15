"""
Unit tests for licensing rule module fixtures and nodes.
"""
from lys.apps.licensing.modules.rule.fixtures import LicenseRuleFixtures
from lys.apps.licensing.modules.rule.nodes import LicenseRuleNode
from lys.core.fixtures import EntityFixtures


class TestLicenseRuleFixtures:
    def test_exists(self):
        assert LicenseRuleFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(LicenseRuleFixtures, EntityFixtures)

    def test_ships_only_the_seat_quota(self):
        """
        A quota lys cannot count belongs to the application, so only the seat
        quota, which counts subscription_user rows, is shipped.
        """
        assert [entry["id"] for entry in LicenseRuleFixtures.data_list] == ["MAX_USERS"]

    def test_has_model(self):
        assert LicenseRuleFixtures.model is not None

    def test_data_list_contains_max_users(self):
        from lys.apps.licensing.consts import MAX_USERS
        ids = [d["id"] for d in LicenseRuleFixtures.data_list]
        assert MAX_USERS in ids


class TestLicenseRuleNode:
    def test_exists(self):
        assert LicenseRuleNode is not None
