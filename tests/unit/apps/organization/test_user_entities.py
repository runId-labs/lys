"""
Unit tests for organization user entities.

Tests User and ClientUserRole entities.
"""

import pytest
from unittest.mock import MagicMock


class TestUserEntity:
    """Tests for User entity structure."""

    def test_user_inherits_from_base_user(self):
        """Test that User inherits from BaseUser."""
        from lys.apps.organization.modules.user.entities import User
        from lys.apps.user_role.modules.user.entities import User as BaseUser

        assert issubclass(User, BaseUser)

    def test_user_has_client_id_column(self):
        """Test that User has client_id column."""
        from lys.apps.organization.modules.user.entities import User

        assert "client_id" in User.__annotations__

    def test_user_has_client_relationship(self):
        """Test that User has client relationship."""
        from lys.apps.organization.modules.user.entities import User
        from tests.mocks.utils import has_relationship

        assert has_relationship(User, "client")

    def test_is_supervisor_returns_true_when_no_client(self):
        """Test that is_supervisor returns True when client_id is None."""
        from lys.apps.organization.modules.user.entities import User

        user = MagicMock(spec=User)
        user.client_id = None

        result = User.is_supervisor.fget(user)

        assert result is True

    def test_is_supervisor_returns_false_when_has_client(self):
        """Test that is_supervisor returns False when client_id is set."""
        from lys.apps.organization.modules.user.entities import User

        user = MagicMock(spec=User)
        user.client_id = "client-123"

        result = User.is_supervisor.fget(user)

        assert result is False

    def test_is_client_user_returns_true_when_has_client(self):
        """Test that is_client_user returns True when client_id is set."""
        from lys.apps.organization.modules.user.entities import User

        user = MagicMock(spec=User)
        user.client_id = "client-123"

        result = User.is_client_user.fget(user)

        assert result is True

    def test_is_client_user_returns_false_when_no_client(self):
        """Test that is_client_user returns False when client_id is None."""
        from lys.apps.organization.modules.user.entities import User

        user = MagicMock(spec=User)
        user.client_id = None

        result = User.is_client_user.fget(user)

        assert result is False

    def test_accessing_organizations_returns_client_id(self):
        """Test that accessing_organizations returns client_id in dict."""
        from lys.apps.organization.modules.user.entities import User

        user = MagicMock(spec=User)
        user.client_id = "client-123"

        result = User.accessing_organizations(user)

        assert result == {"client": ["client-123"]}

    def test_accessing_organizations_returns_empty_when_no_client(self):
        """Test that accessing_organizations returns empty when no client_id."""
        from lys.apps.organization.modules.user.entities import User

        user = MagicMock(spec=User)
        user.client_id = None

        result = User.accessing_organizations(user)

        assert result == {}

    def test_organization_accessing_filters_exists(self):
        """Test that organization_accessing_filters classmethod exists."""
        from lys.apps.organization.modules.user.entities import User

        assert hasattr(User, "organization_accessing_filters")


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

    def test_client_user_role_has_user_relationship(self):
        """Test that ClientUserRole has user relationship."""
        from lys.apps.organization.modules.user.entities import ClientUserRole
        from tests.mocks.utils import has_relationship

        assert has_relationship(ClientUserRole, "user")

    def test_client_user_role_has_role_relationship(self):
        """Test that ClientUserRole has role relationship."""
        from lys.apps.organization.modules.user.entities import ClientUserRole
        from tests.mocks.utils import has_relationship

        assert has_relationship(ClientUserRole, "role")

    def test_level_property_returns_client(self):
        """Test that level property returns 'client' for base implementation."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        role = MagicMock(spec=ClientUserRole)

        result = ClientUserRole.level.fget(role)

        assert result == "client"

    def test_client_id_property_returns_user_client_id(self):
        """Test that client_id property returns user.client_id."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        mock_user = MagicMock()
        mock_user.client_id = "client-456"

        role = MagicMock(spec=ClientUserRole)
        role.user = mock_user

        result = ClientUserRole.client_id.fget(role)

        assert result == "client-456"

    def test_organization_property_returns_user_client(self):
        """Test that organization property returns user.client."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.client = mock_client

        role = MagicMock(spec=ClientUserRole)
        role.user = mock_user

        result = ClientUserRole.organization.fget(role)

        assert result == mock_client

    def test_organization_accessing_filters_exists(self):
        """Test that organization_accessing_filters classmethod exists."""
        from lys.apps.organization.modules.user.entities import ClientUserRole

        assert hasattr(ClientUserRole, "organization_accessing_filters")
