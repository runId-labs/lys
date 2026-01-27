"""
Unit tests for organization user entities.

Tests ClientUser and ClientUserRole entities.
"""

import pytest
from unittest.mock import MagicMock


class TestClientUserEntity:
    """Tests for ClientUser entity structure."""

    def test_client_user_has_tablename(self):
        """Test that ClientUser has correct tablename."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert ClientUser.__tablename__ == "client_user"

    def test_client_user_inherits_from_entity(self):
        """Test that ClientUser inherits from Entity."""
        from lys.apps.organization.modules.user.entities import ClientUser
        from lys.core.entities import Entity

        assert issubclass(ClientUser, Entity)

    def test_client_user_has_user_id_column(self):
        """Test that ClientUser has user_id column."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert "user_id" in ClientUser.__annotations__

    def test_client_user_has_client_id_column(self):
        """Test that ClientUser has client_id column."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert "client_id" in ClientUser.__annotations__

    def test_client_user_has_user_relationship(self):
        """Test that ClientUser has user relationship."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert hasattr(ClientUser, "user")

    def test_client_user_has_client_relationship(self):
        """Test that ClientUser has client relationship."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert hasattr(ClientUser, "client")

    def test_accessing_users_returns_user_id(self):
        """Test that accessing_users returns user_id."""
        from lys.apps.organization.modules.user.entities import ClientUser

        client_user = MagicMock(spec=ClientUser)
        client_user.user_id = "user-123"

        result = ClientUser.accessing_users(client_user)

        assert result == ["user-123"]

    def test_accessing_users_returns_empty_when_no_user_id(self):
        """Test that accessing_users returns empty when no user_id."""
        from lys.apps.organization.modules.user.entities import ClientUser

        client_user = MagicMock(spec=ClientUser)
        client_user.user_id = None

        result = ClientUser.accessing_users(client_user)

        assert result == []

    def test_accessing_organizations_delegates_to_client(self):
        """Test that accessing_organizations delegates to client."""
        from lys.apps.organization.modules.user.entities import ClientUser

        mock_client = MagicMock()
        mock_client.accessing_organizations.return_value = {"client": ["client-1"]}

        client_user = MagicMock(spec=ClientUser)
        client_user.client = mock_client

        result = ClientUser.accessing_organizations(client_user)

        assert result == {"client": ["client-1"]}

    def test_accessing_organizations_returns_empty_when_no_client(self):
        """Test that accessing_organizations returns empty when no client."""
        from lys.apps.organization.modules.user.entities import ClientUser

        client_user = MagicMock(spec=ClientUser)
        client_user.client = None

        result = ClientUser.accessing_organizations(client_user)

        assert result == {}

    def test_user_accessing_filters_exists(self):
        """Test that user_accessing_filters classmethod exists."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert hasattr(ClientUser, "user_accessing_filters")

    def test_organization_accessing_filters_exists(self):
        """Test that organization_accessing_filters classmethod exists."""
        from lys.apps.organization.modules.user.entities import ClientUser

        assert hasattr(ClientUser, "organization_accessing_filters")


class TestClientUserRoleEntity:
    """Tests for ClientUserRole entity structure."""

    def test_client_user_role_has_tablename(self):
        """Test that ClientUserRole has correct tablename."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        assert ClientUserRole.__tablename__ == "client_user_role"

    def test_client_user_role_inherits_from_abstract(self):
        """Test that ClientUserRole inherits from AbstractUserOrganizationRoleEntity."""
        from lys.apps.organization.modules.user.entities import ClientUserRole
        from lys.apps.organization.abstracts import AbstractUserOrganizationRoleEntity

        assert issubclass(ClientUserRole, AbstractUserOrganizationRoleEntity)

    def test_client_user_role_has_client_user_relationship(self):
        """Test that ClientUserRole has client_user relationship."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        assert hasattr(ClientUserRole, "client_user")

    def test_client_user_role_has_role_relationship(self):
        """Test that ClientUserRole has role relationship."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        assert hasattr(ClientUserRole, "role")

    def test_organization_property_exists(self):
        """Test that organization property exists."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        assert hasattr(ClientUserRole, "organization")

    def test_organization_accessing_filters_exists(self):
        """Test that organization_accessing_filters classmethod exists."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        assert hasattr(ClientUserRole, "organization_accessing_filters")
