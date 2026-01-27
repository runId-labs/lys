"""
Unit tests for base one_time_token module fixtures.

Tests fixtures configuration and data.
"""

import pytest


class TestOneTimeTokenTypeFixtures:
    """Tests for OneTimeTokenTypeFixtures."""

    def test_fixture_exists(self):
        """Test OneTimeTokenTypeFixtures class exists."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        assert OneTimeTokenTypeFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test OneTimeTokenTypeFixtures inherits from EntityFixtures."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(OneTimeTokenTypeFixtures, EntityFixtures)

    def test_fixture_has_model(self):
        """Test OneTimeTokenTypeFixtures has model attribute."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert OneTimeTokenTypeFixtures.model == ParametricEntityFixturesModel

    def test_fixture_has_data_list(self):
        """Test OneTimeTokenTypeFixtures has data_list attribute."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        assert hasattr(OneTimeTokenTypeFixtures, "data_list")
        assert isinstance(OneTimeTokenTypeFixtures.data_list, list)

    def test_data_list_contains_password_reset_type(self):
        """Test data_list contains PASSWORD_RESET token type."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

        ids = [item["id"] for item in OneTimeTokenTypeFixtures.data_list]
        assert PASSWORD_RESET_TOKEN_TYPE in ids

    def test_data_list_contains_email_verification_type(self):
        """Test data_list contains EMAIL_VERIFICATION token type."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

        ids = [item["id"] for item in OneTimeTokenTypeFixtures.data_list]
        assert EMAIL_VERIFICATION_TOKEN_TYPE in ids

    def test_data_list_items_have_duration(self):
        """Test each data_list item has duration attribute."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures

        for item in OneTimeTokenTypeFixtures.data_list:
            assert "id" in item
            assert "attributes" in item
            assert "duration" in item["attributes"]

    def test_password_reset_has_30_minute_duration(self):
        """Test password reset token has 30 minute duration."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

        for item in OneTimeTokenTypeFixtures.data_list:
            if item["id"] == PASSWORD_RESET_TOKEN_TYPE:
                assert item["attributes"]["duration"] == 30

    def test_email_verification_has_24_hour_duration(self):
        """Test email verification token has 24 hour duration."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenTypeFixtures
        from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

        for item in OneTimeTokenTypeFixtures.data_list:
            if item["id"] == EMAIL_VERIFICATION_TOKEN_TYPE:
                assert item["attributes"]["duration"] == 1440  # 24 hours in minutes


class TestOneTimeTokenStatusFixtures:
    """Tests for OneTimeTokenStatusFixtures."""

    def test_fixture_exists(self):
        """Test OneTimeTokenStatusFixtures class exists."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        assert OneTimeTokenStatusFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test OneTimeTokenStatusFixtures inherits from EntityFixtures."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(OneTimeTokenStatusFixtures, EntityFixtures)

    def test_fixture_has_model(self):
        """Test OneTimeTokenStatusFixtures has model attribute."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert OneTimeTokenStatusFixtures.model == ParametricEntityFixturesModel

    def test_fixture_has_data_list(self):
        """Test OneTimeTokenStatusFixtures has data_list attribute."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        assert hasattr(OneTimeTokenStatusFixtures, "data_list")
        assert isinstance(OneTimeTokenStatusFixtures.data_list, list)

    def test_data_list_contains_pending_status(self):
        """Test data_list contains PENDING status."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        from lys.apps.base.modules.one_time_token.consts import PENDING_TOKEN_STATUS

        ids = [item["id"] for item in OneTimeTokenStatusFixtures.data_list]
        assert PENDING_TOKEN_STATUS in ids

    def test_data_list_contains_used_status(self):
        """Test data_list contains USED status."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        from lys.apps.base.modules.one_time_token.consts import USED_TOKEN_STATUS

        ids = [item["id"] for item in OneTimeTokenStatusFixtures.data_list]
        assert USED_TOKEN_STATUS in ids

    def test_data_list_contains_revoked_status(self):
        """Test data_list contains REVOKED status."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures
        from lys.apps.base.modules.one_time_token.consts import REVOKED_TOKEN_STATUS

        ids = [item["id"] for item in OneTimeTokenStatusFixtures.data_list]
        assert REVOKED_TOKEN_STATUS in ids

    def test_all_statuses_are_enabled(self):
        """Test all statuses are enabled."""
        from lys.apps.base.modules.one_time_token.fixtures import OneTimeTokenStatusFixtures

        for item in OneTimeTokenStatusFixtures.data_list:
            assert item["attributes"]["enabled"] is True
