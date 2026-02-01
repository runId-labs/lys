"""
Unit tests for organization auth services.

Tests OrganizationAuthService class.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestOrganizationAuthServiceStructure:
    """Tests for OrganizationAuthService class structure."""

    def test_inherits_from_role_auth_service(self):
        """Test that OrganizationAuthService inherits from RoleAuthService."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        from lys.apps.user_role.modules.auth.services import RoleAuthService

        assert issubclass(OrganizationAuthService, RoleAuthService)

    def test_has_generate_access_claims_method(self):
        """Test that OrganizationAuthService has generate_access_claims method."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        import inspect

        assert hasattr(OrganizationAuthService, "generate_access_claims")
        assert inspect.iscoroutinefunction(OrganizationAuthService.generate_access_claims)

    def test_has_get_user_organizations_method(self):
        """Test that OrganizationAuthService has _get_user_organizations method."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        import inspect

        assert hasattr(OrganizationAuthService, "_get_user_organizations")
        assert inspect.iscoroutinefunction(OrganizationAuthService._get_user_organizations)

    def test_has_get_owner_webservices_method(self):
        """Test that OrganizationAuthService has _get_owner_webservices method."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        import inspect

        assert hasattr(OrganizationAuthService, "_get_owner_webservices")
        assert inspect.iscoroutinefunction(OrganizationAuthService._get_owner_webservices)

    def test_has_get_client_user_role_webservices_method(self):
        """Test that OrganizationAuthService has _get_client_user_role_webservices method."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        import inspect

        assert hasattr(OrganizationAuthService, "_get_client_user_role_webservices")
        assert inspect.iscoroutinefunction(OrganizationAuthService._get_client_user_role_webservices)


class TestOrganizationAuthServiceGenerateAccessClaims:
    """Tests for OrganizationAuthService.generate_access_claims method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def super_user(self):
        """Create a super user mock."""
        user = MagicMock()
        user.id = "admin-456"
        user.is_super_user = True
        return user

    @pytest.fixture
    def regular_user(self):
        """Create a regular user mock."""
        user = MagicMock()
        user.id = "user-123"
        user.is_super_user = False
        return user

    @pytest.mark.asyncio
    async def test_super_user_skips_organizations(self, mock_session, super_user):
        """Test that super users don't get organizations added."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        parent_claims = {
            "sub": "admin-456",
            "is_super_user": True,
            "webservices": {}
        }

        with patch.object(OrganizationAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(OrganizationAuthService, '_get_user_organizations',
                              new_callable=AsyncMock) as mock_get_orgs:
                result = await OrganizationAuthService.generate_access_claims(super_user, mock_session)

        # Should not call _get_user_organizations for super users
        mock_get_orgs.assert_not_called()
        assert result == parent_claims
        assert "organizations" not in result

    @pytest.mark.asyncio
    async def test_regular_user_gets_organizations(self, mock_session, regular_user):
        """Test that regular users get organizations added."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        parent_claims = {
            "sub": "user-123",
            "is_super_user": False,
            "webservices": {}
        }

        mock_organizations = {
            "client-1": {
                "level": "client",
                "webservices": ["manage_billing"]
            }
        }

        with patch.object(OrganizationAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(OrganizationAuthService, '_get_user_organizations',
                              new_callable=AsyncMock, return_value=mock_organizations):
                result = await OrganizationAuthService.generate_access_claims(regular_user, mock_session)

        assert "organizations" in result
        assert result["organizations"] == mock_organizations

    @pytest.mark.asyncio
    async def test_regular_user_without_organizations(self, mock_session, regular_user):
        """Test regular user without any organizations."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        parent_claims = {
            "sub": "user-123",
            "is_super_user": False,
            "webservices": {}
        }

        with patch.object(OrganizationAuthService.__bases__[0], 'generate_access_claims',
                          new_callable=AsyncMock, return_value=parent_claims):
            with patch.object(OrganizationAuthService, '_get_user_organizations',
                              new_callable=AsyncMock, return_value={}):
                result = await OrganizationAuthService.generate_access_claims(regular_user, mock_session)

        # organizations key should not be added if empty
        assert "organizations" not in result
