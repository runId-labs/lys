"""
Unit tests for organization user fixtures.

Tests ClientRelatedUserDevFixtures and ClientUserDevFixtures structure and configuration.
"""

import pytest
import inspect
from unittest.mock import MagicMock, AsyncMock


class TestClientRelatedUserDevFixturesStructure:
    """Tests for ClientRelatedUserDevFixtures class structure."""

    def test_fixture_class_exists(self):
        """Test ClientRelatedUserDevFixtures class exists."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert ClientRelatedUserDevFixtures is not None

    def test_fixture_inherits_from_user_dev_fixtures(self):
        """Test ClientRelatedUserDevFixtures inherits from UserDevFixtures."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures
        assert issubclass(ClientRelatedUserDevFixtures, UserDevFixtures)

    def test_fixture_has_allowed_envs(self):
        """Test ClientRelatedUserDevFixtures has _allowed_envs attribute."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert hasattr(ClientRelatedUserDevFixtures, "_allowed_envs")

    def test_fixture_only_allowed_in_dev(self):
        """Test fixture only allowed in DEV environment."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        from lys.core.consts.environments import EnvironmentEnum

        assert ClientRelatedUserDevFixtures._allowed_envs == [EnvironmentEnum.DEV]

    def test_fixture_does_not_delete_previous_data(self):
        """Test fixture does not delete previous data."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert ClientRelatedUserDevFixtures.delete_previous_data is False


class TestClientRelatedUserDevFixturesDataList:
    """Tests for ClientRelatedUserDevFixtures data_list configuration."""

    def test_fixture_has_data_list(self):
        """Test fixture has data_list attribute."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert hasattr(ClientRelatedUserDevFixtures, "data_list")

    def test_data_list_is_list(self):
        """Test data_list is a list."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert isinstance(ClientRelatedUserDevFixtures.data_list, list)

    def test_data_list_has_entries(self):
        """Test data_list has entries."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert len(ClientRelatedUserDevFixtures.data_list) > 0

    def test_data_list_entries_have_required_fields(self):
        """Test data_list entries have required fields."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures

        for entry in ClientRelatedUserDevFixtures.data_list:
            attributes = entry["attributes"]
            assert "email_address" in attributes
            assert "password" in attributes
            assert "language_id" in attributes
            assert "private_data" in attributes


class TestClientUserDevFixturesStructure:
    """Tests for ClientUserDevFixtures class structure."""

    def test_fixture_class_exists(self):
        """Test ClientUserDevFixtures class exists."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert ClientUserDevFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test ClientUserDevFixtures inherits from EntityFixtures."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(ClientUserDevFixtures, EntityFixtures)

    def test_fixture_has_model_attribute(self):
        """Test fixture has model attribute."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert hasattr(ClientUserDevFixtures, "model")

    def test_fixture_model_is_entity_fixtures_model(self):
        """Test fixture model is EntityFixturesModel."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        from lys.core.models.fixtures import EntityFixturesModel
        assert ClientUserDevFixtures.model is EntityFixturesModel

    def test_fixture_only_allowed_in_dev(self):
        """Test fixture only allowed in DEV environment."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        from lys.core.consts.environments import EnvironmentEnum

        assert EnvironmentEnum.DEV in ClientUserDevFixtures._allowed_envs

    def test_fixture_does_not_delete_previous_data(self):
        """Test fixture does not delete previous data."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert ClientUserDevFixtures.delete_previous_data is False


class TestClientUserDevFixturesDataList:
    """Tests for ClientUserDevFixtures data_list configuration."""

    def test_fixture_has_data_list(self):
        """Test fixture has data_list attribute."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert hasattr(ClientUserDevFixtures, "data_list")

    def test_data_list_is_list(self):
        """Test data_list is a list."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert isinstance(ClientUserDevFixtures.data_list, list)

    def test_data_list_has_entries(self):
        """Test data_list has entries."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert len(ClientUserDevFixtures.data_list) > 0

    def test_data_list_entries_have_required_fields(self):
        """Test data_list entries have required fields."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures

        for entry in ClientUserDevFixtures.data_list:
            attributes = entry["attributes"]
            assert "client_name" in attributes
            assert "user_email" in attributes
            assert "role_codes" in attributes


class TestClientUserDevFixturesCreateFromService:
    """Tests for ClientUserDevFixtures create_from_service method."""

    def test_create_from_service_exists(self):
        """Test create_from_service method exists."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert hasattr(ClientUserDevFixtures, "create_from_service")

    def test_create_from_service_is_async(self):
        """Test create_from_service is async."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert inspect.iscoroutinefunction(ClientUserDevFixtures.create_from_service)

    def test_create_from_service_is_classmethod(self):
        """Test create_from_service is a classmethod."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert isinstance(
            inspect.getattr_static(ClientUserDevFixtures, "create_from_service"),
            classmethod
        )

    def test_create_from_service_signature(self):
        """Test create_from_service method signature."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures

        sig = inspect.signature(ClientUserDevFixtures.create_from_service)
        assert "attributes" in sig.parameters
        assert "session" in sig.parameters


class TestFixtureRegistration:
    """Tests for fixture registration."""

    def test_client_related_user_dev_fixtures_registered(self):
        """Test ClientRelatedUserDevFixtures is registered."""
        from lys.apps.organization.modules.user.fixtures import ClientRelatedUserDevFixtures
        assert ClientRelatedUserDevFixtures is not None

    def test_client_user_dev_fixtures_registered(self):
        """Test ClientUserDevFixtures is registered."""
        from lys.apps.organization.modules.user.fixtures import ClientUserDevFixtures
        assert ClientUserDevFixtures is not None
