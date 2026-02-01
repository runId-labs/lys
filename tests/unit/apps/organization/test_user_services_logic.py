"""
Unit tests for organization user services logic with mocks.

Tests UserService and ClientUserService method execution.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestClientUserServiceCreateClientUser:
    """Tests for ClientUserService.create_client_user method logic."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_creates_user_and_client_user(self, mock_session):
        """Test that method creates user and client_user relationship."""
        from lys.apps.organization.modules.user.services import ClientUserService

        # Mock user service
        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_user_service = MagicMock()
        mock_user_service.create_user = AsyncMock(return_value=mock_user)

        # Mock client_user entity class
        mock_client_user = MagicMock()
        mock_client_user.id = "client-user-456"
        mock_client_user_class = MagicMock(return_value=mock_client_user)

        with patch.object(ClientUserService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_user_service

            with patch.object(ClientUserService, 'entity_class', mock_client_user_class):
                with patch.object(ClientUserService, '_assign_roles', new_callable=AsyncMock) as mock_assign:
                    result = await ClientUserService.create_client_user(
                        session=mock_session,
                        client_id="client-789",
                        email="test@example.com",
                        password="password123",
                        language_id="en"
                    )

        # Verify user was created
        mock_user_service.create_user.assert_called_once()

        # Verify client_user was created
        mock_client_user_class.assert_called_once_with(
            user_id="user-123",
            client_id="client-789"
        )

        # Verify session.add was called
        mock_session.add.assert_called()

        # No roles provided, so _assign_roles should not be called
        mock_assign.assert_not_called()

    @pytest.mark.asyncio
    async def test_assigns_roles_when_provided(self, mock_session):
        """Test that roles are assigned when role_codes provided."""
        from lys.apps.organization.modules.user.services import ClientUserService

        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_user_service = MagicMock()
        mock_user_service.create_user = AsyncMock(return_value=mock_user)

        mock_client_user = MagicMock()
        mock_client_user.id = "client-user-456"
        mock_client_user_class = MagicMock(return_value=mock_client_user)

        with patch.object(ClientUserService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_user_service

            with patch.object(ClientUserService, 'entity_class', mock_client_user_class):
                with patch.object(ClientUserService, '_assign_roles', new_callable=AsyncMock) as mock_assign:
                    await ClientUserService.create_client_user(
                        session=mock_session,
                        client_id="client-789",
                        email="test@example.com",
                        password="password123",
                        language_id="en",
                        role_codes=["admin", "user"]
                    )

        # _assign_roles should be called with role_codes
        mock_assign.assert_called_once_with(mock_client_user, ["admin", "user"], mock_session)


class TestClientUserServiceUpdateClientUserRoles:
    """Tests for ClientUserService.update_client_user_roles method logic."""

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
        from lys.apps.organization.modules.user.services import ClientUserService

        # Mock existing role
        mock_existing_role = MagicMock()
        mock_existing_role.role = MagicMock()
        mock_existing_role.role.id = "admin"

        mock_client_user = MagicMock()
        mock_client_user.id = "client-user-123"
        mock_client_user.client_user_roles = [mock_existing_role]

        await ClientUserService.update_client_user_roles(
            mock_client_user,
            [],  # Empty list removes all roles
            mock_session
        )

        # Should delete the existing role
        mock_session.delete.assert_called_once_with(mock_existing_role)

    @pytest.mark.asyncio
    async def test_no_change_when_same_roles(self, mock_session):
        """Test that no changes when roles are the same."""
        from lys.apps.organization.modules.user.services import ClientUserService

        mock_existing_role = MagicMock()
        mock_existing_role.role = MagicMock()
        mock_existing_role.role.id = "admin"

        mock_client_user = MagicMock()
        mock_client_user.id = "client-user-123"
        mock_client_user.client_user_roles = [mock_existing_role]

        await ClientUserService.update_client_user_roles(
            mock_client_user,
            ["admin"],  # Same as existing
            mock_session
        )

        # Should not add or delete anything
        mock_session.add.assert_not_called()
        mock_session.delete.assert_not_called()


class TestUserServiceMethodSignatures:
    """Tests for UserService method signatures."""

    def test_get_user_organization_roles_is_async(self):
        """Test that get_user_organization_roles is async."""
        import inspect
        from lys.apps.organization.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService.get_user_organization_roles)

    def test_get_user_organization_roles_signature(self):
        """Test get_user_organization_roles method signature."""
        import inspect
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.get_user_organization_roles)
        assert "user_id" in sig.parameters
        assert "session" in sig.parameters
        assert "webservice_id" in sig.parameters


class TestClientUserServiceMethodSignatures:
    """Tests for ClientUserService method signatures."""

    def test_assign_roles_is_async(self):
        """Test that _assign_roles is async."""
        import inspect
        from lys.apps.organization.modules.user.services import ClientUserService

        assert inspect.iscoroutinefunction(ClientUserService._assign_roles)

    def test_assign_roles_signature(self):
        """Test _assign_roles method signature."""
        import inspect
        from lys.apps.organization.modules.user.services import ClientUserService

        sig = inspect.signature(ClientUserService._assign_roles)
        assert "client_user" in sig.parameters
        assert "role_codes" in sig.parameters
        assert "session" in sig.parameters
