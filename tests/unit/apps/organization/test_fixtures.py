"""
Unit tests for organization fixture classes.

Tests AccessLevelFixtures and OrganizationRoleFixtures.
"""

import pytest


class TestAccessLevelFixtures:
    """Tests for AccessLevelFixtures class."""

    def test_access_level_fixtures_exists(self):
        """Test that AccessLevelFixtures class exists."""
        from lys.apps.organization.modules.access_level.fixtures import AccessLevelFixtures

        assert AccessLevelFixtures is not None

    def test_access_level_fixtures_has_model(self):
        """Test that AccessLevelFixtures has model attribute."""
        from lys.apps.organization.modules.access_level.fixtures import AccessLevelFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel

        assert AccessLevelFixtures.model == ParametricEntityFixturesModel

    def test_access_level_fixtures_has_data_list(self):
        """Test that AccessLevelFixtures has data_list attribute."""
        from lys.apps.organization.modules.access_level.fixtures import AccessLevelFixtures

        assert hasattr(AccessLevelFixtures, "data_list")
        assert isinstance(AccessLevelFixtures.data_list, list)

    def test_access_level_fixtures_contains_organization_role(self):
        """Test that data_list contains ORGANIZATION_ROLE access level."""
        from lys.apps.organization.modules.access_level.fixtures import AccessLevelFixtures
        from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL

        access_level_ids = [item["id"] for item in AccessLevelFixtures.data_list]
        assert ORGANIZATION_ROLE_ACCESS_LEVEL in access_level_ids

    def test_access_level_fixtures_does_not_delete_previous(self):
        """Test that delete_previous_data is False."""
        from lys.apps.organization.modules.access_level.fixtures import AccessLevelFixtures

        assert AccessLevelFixtures.delete_previous_data is False


class TestOrganizationRoleFixtures:
    """Tests for OrganizationRoleFixtures class."""

    def test_organization_role_fixtures_exists(self):
        """Test that OrganizationRoleFixtures class exists."""
        from lys.apps.organization.modules.role.fixtures import OrganizationRoleFixtures

        assert OrganizationRoleFixtures is not None

    def test_organization_role_fixtures_inherits_role_fixtures(self):
        """Test that OrganizationRoleFixtures inherits from RoleFixtures."""
        from lys.apps.organization.modules.role.fixtures import OrganizationRoleFixtures
        from lys.apps.user_role.modules.role.fixtures import RoleFixtures

        assert issubclass(OrganizationRoleFixtures, RoleFixtures)

    def test_organization_role_fixtures_has_data_list(self):
        """Test that OrganizationRoleFixtures has data_list attribute."""
        from lys.apps.organization.modules.role.fixtures import OrganizationRoleFixtures

        assert hasattr(OrganizationRoleFixtures, "data_list")
        assert isinstance(OrganizationRoleFixtures.data_list, list)

    def test_organization_role_fixtures_contains_client_admin_role(self):
        """Test that data_list contains CLIENT_ADMIN_ROLE."""
        from lys.apps.organization.modules.role.fixtures import OrganizationRoleFixtures
        from lys.apps.organization.consts import CLIENT_ADMIN_ROLE

        role_ids = [item["id"] for item in OrganizationRoleFixtures.data_list]
        assert CLIENT_ADMIN_ROLE in role_ids

    def test_organization_role_fixtures_contains_user_admin_role(self):
        """Test that data_list contains USER_ADMIN_ROLE."""
        from lys.apps.organization.modules.role.fixtures import OrganizationRoleFixtures
        from lys.apps.user_role.consts import USER_ADMIN_ROLE

        role_ids = [item["id"] for item in OrganizationRoleFixtures.data_list]
        assert USER_ADMIN_ROLE in role_ids


class TestUserAdminRoleOrganizationWebservices:
    """Tests for USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES constant."""

    def test_webservices_list_exists(self):
        """Test that USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES exists."""
        from lys.apps.organization.modules.role.fixtures import USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES

        assert isinstance(USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES, list)

    def test_webservices_includes_base_webservices(self):
        """Test that list includes base USER_ADMIN_ROLE_WEBSERVICES."""
        from lys.apps.organization.modules.role.fixtures import USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES
        from lys.apps.user_role.modules.role.fixtures import USER_ADMIN_ROLE_WEBSERVICES

        for ws in USER_ADMIN_ROLE_WEBSERVICES:
            assert ws in USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES

    def test_webservices_includes_organization_specific(self):
        """Test that list includes organization-specific webservices."""
        from lys.apps.organization.modules.role.fixtures import USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES

        assert "all_clients" in USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES
        assert "all_client_users" in USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES
        assert "client_user" in USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES
        assert "create_client_user" in USER_ADMIN_ROLE_ORGANIZATION_WEBSERVICES
