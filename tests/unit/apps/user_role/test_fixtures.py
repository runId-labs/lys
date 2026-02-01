"""
Unit tests for user_role fixture classes.

Tests RoleFixtures, AccessLevelFixtures, and RoleUserDevFixtures.
"""

import pytest


class TestRoleFixtures:
    """Tests for RoleFixtures class."""

    def test_role_fixtures_exists(self):
        """Test that RoleFixtures class exists."""
        from lys.apps.user_role.modules.role.fixtures import RoleFixtures

        assert RoleFixtures is not None

    def test_role_fixtures_has_model(self):
        """Test that RoleFixtures has model attribute."""
        from lys.apps.user_role.modules.role.fixtures import RoleFixtures
        from lys.apps.user_role.models import RoleFixturesModel

        assert RoleFixtures.model == RoleFixturesModel

    def test_role_fixtures_has_data_list(self):
        """Test that RoleFixtures has data_list attribute."""
        from lys.apps.user_role.modules.role.fixtures import RoleFixtures

        assert hasattr(RoleFixtures, "data_list")
        assert isinstance(RoleFixtures.data_list, list)

    def test_role_fixtures_data_contains_user_admin_role(self):
        """Test that data_list contains USER_ADMIN_ROLE."""
        from lys.apps.user_role.modules.role.fixtures import RoleFixtures
        from lys.apps.user_role.consts import USER_ADMIN_ROLE

        role_ids = [item["id"] for item in RoleFixtures.data_list]
        assert USER_ADMIN_ROLE in role_ids

    def test_role_fixtures_has_format_role_webservices(self):
        """Test that RoleFixtures has format_role_webservices method."""
        from lys.apps.user_role.modules.role.fixtures import RoleFixtures
        import inspect

        assert hasattr(RoleFixtures, "format_role_webservices")
        assert inspect.iscoroutinefunction(RoleFixtures.format_role_webservices)

    def test_user_admin_role_webservices_list(self):
        """Test USER_ADMIN_ROLE_WEBSERVICES contains expected webservices."""
        from lys.apps.user_role.modules.role.fixtures import USER_ADMIN_ROLE_WEBSERVICES

        assert isinstance(USER_ADMIN_ROLE_WEBSERVICES, list)
        assert "create_user" in USER_ADMIN_ROLE_WEBSERVICES
        assert "user" in USER_ADMIN_ROLE_WEBSERVICES
        assert "update_user_roles" in USER_ADMIN_ROLE_WEBSERVICES


class TestAccessLevelFixtures:
    """Tests for AccessLevelFixtures class."""

    def test_access_level_fixtures_exists(self):
        """Test that AccessLevelFixtures class exists."""
        from lys.apps.user_role.modules.access_level.fixtures import AccessLevelFixtures

        assert AccessLevelFixtures is not None

    def test_access_level_fixtures_has_model(self):
        """Test that AccessLevelFixtures has model attribute."""
        from lys.apps.user_role.modules.access_level.fixtures import AccessLevelFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel

        assert AccessLevelFixtures.model == ParametricEntityFixturesModel

    def test_access_level_fixtures_has_data_list(self):
        """Test that AccessLevelFixtures has data_list attribute."""
        from lys.apps.user_role.modules.access_level.fixtures import AccessLevelFixtures

        assert hasattr(AccessLevelFixtures, "data_list")
        assert isinstance(AccessLevelFixtures.data_list, list)

    def test_access_level_fixtures_contains_role_access_level(self):
        """Test that data_list contains ROLE access level."""
        from lys.apps.user_role.modules.access_level.fixtures import AccessLevelFixtures
        from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL

        access_level_ids = [item["id"] for item in AccessLevelFixtures.data_list]
        assert ROLE_ACCESS_LEVEL in access_level_ids

    def test_access_level_fixtures_does_not_delete_previous(self):
        """Test that delete_previous_data is False."""
        from lys.apps.user_role.modules.access_level.fixtures import AccessLevelFixtures

        assert AccessLevelFixtures.delete_previous_data is False


class TestRoleUserDevFixtures:
    """Tests for RoleUserDevFixtures class."""

    def test_role_user_dev_fixtures_exists(self):
        """Test that RoleUserDevFixtures class exists."""
        from lys.apps.user_role.modules.user.fixtures import RoleUserDevFixtures

        assert RoleUserDevFixtures is not None

    def test_role_user_dev_fixtures_inherits_user_dev_fixtures(self):
        """Test that RoleUserDevFixtures inherits from UserDevFixtures."""
        from lys.apps.user_role.modules.user.fixtures import RoleUserDevFixtures
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures

        assert issubclass(RoleUserDevFixtures, UserDevFixtures)

    def test_role_user_dev_fixtures_has_data_list(self):
        """Test that RoleUserDevFixtures has data_list attribute."""
        from lys.apps.user_role.modules.user.fixtures import RoleUserDevFixtures

        assert hasattr(RoleUserDevFixtures, "data_list")
        assert isinstance(RoleUserDevFixtures.data_list, list)

    def test_role_user_dev_fixtures_does_not_delete_previous(self):
        """Test that delete_previous_data is False."""
        from lys.apps.user_role.modules.user.fixtures import RoleUserDevFixtures

        assert RoleUserDevFixtures.delete_previous_data is False

    def test_role_user_dev_fixtures_has_format_roles_method(self):
        """Test that RoleUserDevFixtures has format_roles method."""
        from lys.apps.user_role.modules.user.fixtures import RoleUserDevFixtures
        import inspect

        assert hasattr(RoleUserDevFixtures, "format_roles")
        assert inspect.iscoroutinefunction(RoleUserDevFixtures.format_roles)

    def test_role_user_dev_fixtures_data_contains_admin_user(self):
        """Test that data_list contains admin user."""
        from lys.apps.user_role.modules.user.fixtures import RoleUserDevFixtures

        assert len(RoleUserDevFixtures.data_list) > 0
        admin_data = RoleUserDevFixtures.data_list[0]
        assert "admin_user@lys-test.fr" in admin_data["attributes"]["email_address"]
