"""
Unit tests for base emailing module fixtures.

Tests fixtures configuration and data.
"""

import pytest


class TestEmailingStatusFixtures:
    """Tests for EmailingStatusFixtures."""

    def test_fixture_exists(self):
        """Test EmailingStatusFixtures class exists."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        assert EmailingStatusFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test EmailingStatusFixtures inherits from EntityFixtures."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(EmailingStatusFixtures, EntityFixtures)

    def test_fixture_has_model(self):
        """Test EmailingStatusFixtures has model attribute."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert EmailingStatusFixtures.model == ParametricEntityFixturesModel

    def test_fixture_has_data_list(self):
        """Test EmailingStatusFixtures has data_list attribute."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        assert hasattr(EmailingStatusFixtures, "data_list")
        assert isinstance(EmailingStatusFixtures.data_list, list)

    def test_data_list_contains_waiting_status(self):
        """Test data_list contains WAITING status."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        from lys.apps.base.modules.emailing.consts import WAITING_EMAILING_STATUS

        ids = [item["id"] for item in EmailingStatusFixtures.data_list]
        assert WAITING_EMAILING_STATUS in ids

    def test_data_list_contains_sent_status(self):
        """Test data_list contains SENT status."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        from lys.apps.base.modules.emailing.consts import SENT_EMAILING_STATUS

        ids = [item["id"] for item in EmailingStatusFixtures.data_list]
        assert SENT_EMAILING_STATUS in ids

    def test_data_list_contains_error_status(self):
        """Test data_list contains ERROR status."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures
        from lys.apps.base.modules.emailing.consts import ERROR_EMAILING_STATUS

        ids = [item["id"] for item in EmailingStatusFixtures.data_list]
        assert ERROR_EMAILING_STATUS in ids

    def test_all_statuses_are_enabled(self):
        """Test all statuses are enabled."""
        from lys.apps.base.modules.emailing.fixtures import EmailingStatusFixtures

        for item in EmailingStatusFixtures.data_list:
            assert item["attributes"]["enabled"] is True
