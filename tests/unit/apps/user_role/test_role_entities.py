"""
Unit tests for role entities.

Tests Role and RoleWebservice entity methods.
"""

import pytest
from unittest.mock import MagicMock


class TestRoleGetWebserviceIds:
    """Tests for Role.get_webservice_ids method."""

    def test_get_webservice_ids_returns_list(self):
        """Test that get_webservice_ids returns a list."""
        from lys.apps.user_role.modules.role.entities import Role

        role = Role()
        role.role_webservices = []

        result = role.get_webservice_ids()

        assert isinstance(result, list)

    def test_get_webservice_ids_with_webservices(self):
        """Test get_webservice_ids with assigned webservices."""
        from lys.apps.user_role.modules.role.entities import Role

        # Create mock role_webservices
        rw1 = MagicMock()
        rw1.webservice_id = "get_users"

        rw2 = MagicMock()
        rw2.webservice_id = "update_user"

        rw3 = MagicMock()
        rw3.webservice_id = "delete_user"

        role = Role()
        role.role_webservices = [rw1, rw2, rw3]

        result = role.get_webservice_ids()

        assert result == ["get_users", "update_user", "delete_user"]

    def test_get_webservice_ids_empty(self):
        """Test get_webservice_ids with no webservices."""
        from lys.apps.user_role.modules.role.entities import Role

        role = Role()
        role.role_webservices = []

        result = role.get_webservice_ids()

        assert result == []

    def test_get_webservice_ids_preserves_order(self):
        """Test that get_webservice_ids preserves order."""
        from lys.apps.user_role.modules.role.entities import Role

        # Create mock role_webservices in specific order
        webservice_ids = ["ws_c", "ws_a", "ws_b"]
        role_webservices = []

        for ws_id in webservice_ids:
            rw = MagicMock()
            rw.webservice_id = ws_id
            role_webservices.append(rw)

        role = Role()
        role.role_webservices = role_webservices

        result = role.get_webservice_ids()

        assert result == webservice_ids


class TestRoleEntity:
    """Tests for Role entity structure."""

    def test_role_has_tablename(self):
        """Test that Role has correct tablename."""
        from lys.apps.user_role.modules.role.entities import Role

        assert Role.__tablename__ == "role"

    def test_role_inherits_parametric_entity(self):
        """Test that Role inherits from ParametricEntity."""
        from lys.apps.user_role.modules.role.entities import Role
        from lys.core.entities import ParametricEntity

        assert issubclass(Role, ParametricEntity)


class TestRoleWebserviceEntity:
    """Tests for RoleWebservice entity structure."""

    def test_role_webservice_has_tablename(self):
        """Test that RoleWebservice has correct tablename."""
        from lys.apps.user_role.modules.role.entities import RoleWebservice

        assert RoleWebservice.__tablename__ == "role_webservice"

    def test_role_webservice_inherits_entity(self):
        """Test that RoleWebservice inherits from Entity."""
        from lys.apps.user_role.modules.role.entities import RoleWebservice
        from lys.core.entities import Entity

        assert issubclass(RoleWebservice, Entity)
