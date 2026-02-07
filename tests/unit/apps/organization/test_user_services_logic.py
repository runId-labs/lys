"""
Unit tests for organization user services logic with mocks.

Tests UserService method signatures and structure.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import pytest
import inspect
from unittest.mock import MagicMock, AsyncMock, patch


class TestUserServiceMethodSignatures:
    """Tests for UserService method signatures."""

    def test_get_user_organization_roles_is_async(self):
        """Test that get_user_organization_roles is async."""
        from lys.apps.organization.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService.get_user_organization_roles)

    def test_get_user_organization_roles_signature(self):
        """Test get_user_organization_roles method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.get_user_organization_roles)
        assert "user_id" in sig.parameters
        assert "session" in sig.parameters
        assert "webservice_id" in sig.parameters

    def test_create_client_user_is_async(self):
        """Test that create_client_user is async."""
        from lys.apps.organization.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService.create_client_user)

    def test_create_client_user_signature(self):
        """Test create_client_user method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.create_client_user)
        assert "session" in sig.parameters
        assert "client_id" in sig.parameters
        assert "email" in sig.parameters
        assert "password" in sig.parameters
        assert "language_id" in sig.parameters

    def test_update_client_user_roles_is_async(self):
        """Test that update_client_user_roles is async."""
        from lys.apps.organization.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService.update_client_user_roles)

    def test_update_client_user_roles_signature(self):
        """Test update_client_user_roles method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.update_client_user_roles)
        assert "user" in sig.parameters
        assert "role_codes" in sig.parameters
        assert "session" in sig.parameters

    def test_assign_client_user_roles_is_async(self):
        """Test that _assign_client_user_roles is async."""
        from lys.apps.organization.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService._assign_client_user_roles)

    def test_assign_client_user_roles_signature(self):
        """Test _assign_client_user_roles method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService._assign_client_user_roles)
        assert "user" in sig.parameters
        assert "role_codes" in sig.parameters
        assert "session" in sig.parameters


class TestUserServiceUpdateClientUserRolesLogic:
    """Tests for UserService.update_client_user_roles method logic."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.delete = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_removes_roles_when_empty_list(self, mock_session):
        """Test that all roles are removed when empty list provided."""
        from lys.apps.organization.modules.user.services import UserService

        # Mock existing role
        mock_existing_role = MagicMock()
        mock_existing_role.role = MagicMock()
        mock_existing_role.role.id = "admin"

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.client_user_roles = [mock_existing_role]

        await UserService.update_client_user_roles(
            mock_user,
            [],  # Empty list removes all roles
            mock_session
        )

        # Should delete the existing role
        mock_session.delete.assert_called_once_with(mock_existing_role)

    @pytest.mark.asyncio
    async def test_no_change_when_same_roles(self, mock_session):
        """Test that no changes when roles are the same."""
        from lys.apps.organization.modules.user.services import UserService

        mock_existing_role = MagicMock()
        mock_existing_role.role = MagicMock()
        mock_existing_role.role.id = "admin"

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.client_user_roles = [mock_existing_role]

        await UserService.update_client_user_roles(
            mock_user,
            ["admin"],  # Same as existing
            mock_session
        )

        # Should not add or delete anything
        mock_session.add.assert_not_called()
        mock_session.delete.assert_not_called()
