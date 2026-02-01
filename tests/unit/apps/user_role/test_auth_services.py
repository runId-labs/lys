"""
Unit tests for user_role RoleAuthService.

Tests the authentication service with role-based JWT claims.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRoleAuthServiceGenerateAccessClaims:
    """Tests for RoleAuthService.generate_access_claims method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def regular_user(self):
        """Create a regular user mock."""
        user = MagicMock()
        user.id = "user-123"
        user.is_super_user = False
        return user

    @pytest.fixture
    def super_user(self):
        """Create a super user mock."""
        user = MagicMock()
        user.id = "admin-456"
        user.is_super_user = True
        return user

    @pytest.mark.asyncio
    async def test_super_user_skips_role_webservices(self, mock_session, super_user):
        """Test that super users don't get role webservices added."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        # Mock parent generate_access_claims
        parent_claims = {
            "sub": "admin-456",
            "is_super_user": True,
            "webservices": {}
        }

        with patch.object(RoleAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(RoleAuthService, '_get_user_role_webservices',
                              new_callable=AsyncMock) as mock_get_roles:
                result = await RoleAuthService.generate_access_claims(super_user, mock_session)

        # Should not call _get_user_role_webservices for super users
        mock_get_roles.assert_not_called()
        assert result == parent_claims

    @pytest.mark.asyncio
    async def test_regular_user_gets_role_webservices(self, mock_session, regular_user):
        """Test that regular users get role webservices added."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        # Mock parent claims
        parent_claims = {
            "sub": "user-123",
            "is_super_user": False,
            "webservices": {"base_webservice": "owner"}
        }

        # Mock role webservices
        role_webservices = ["get_users", "update_profile"]

        with patch.object(RoleAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(RoleAuthService, '_get_user_role_webservices',
                              new_callable=AsyncMock, return_value=role_webservices):
                result = await RoleAuthService.generate_access_claims(regular_user, mock_session)

        # Role webservices should be added with "full" access
        assert result["webservices"]["get_users"] == "full"
        assert result["webservices"]["update_profile"] == "full"
        # Base webservice should still be there
        assert result["webservices"]["base_webservice"] == "owner"

    @pytest.mark.asyncio
    async def test_role_access_upgrades_owner_to_full(self, mock_session, regular_user):
        """Test that role access upgrades 'owner' to 'full'."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        # Mock parent claims with owner access
        parent_claims = {
            "sub": "user-123",
            "is_super_user": False,
            "webservices": {"shared_webservice": "owner"}
        }

        # Role also grants access to same webservice
        role_webservices = ["shared_webservice"]

        with patch.object(RoleAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(RoleAuthService, '_get_user_role_webservices',
                              new_callable=AsyncMock, return_value=role_webservices):
                result = await RoleAuthService.generate_access_claims(regular_user, mock_session)

        # Should be upgraded to "full"
        assert result["webservices"]["shared_webservice"] == "full"

    @pytest.mark.asyncio
    async def test_empty_role_webservices(self, mock_session, regular_user):
        """Test handling of user with no role webservices."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        parent_claims = {
            "sub": "user-123",
            "is_super_user": False,
            "webservices": {"base_ws": "full"}
        }

        with patch.object(RoleAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(RoleAuthService, '_get_user_role_webservices',
                              new_callable=AsyncMock, return_value=[]):
                result = await RoleAuthService.generate_access_claims(regular_user, mock_session)

        # Should have only base webservices
        assert result["webservices"] == {"base_ws": "full"}


class TestRoleAuthServiceInheritance:
    """Tests for RoleAuthService class structure."""

    def test_inherits_from_auth_service(self):
        """Test that RoleAuthService inherits from AuthService."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService
        from lys.apps.user_auth.modules.auth.services import AuthService

        assert issubclass(RoleAuthService, AuthService)

    def test_has_generate_access_claims_method(self):
        """Test that RoleAuthService has generate_access_claims method."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        assert hasattr(RoleAuthService, 'generate_access_claims')

    def test_has_get_user_role_webservices_method(self):
        """Test that RoleAuthService has _get_user_role_webservices method."""
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        assert hasattr(RoleAuthService, '_get_user_role_webservices')
