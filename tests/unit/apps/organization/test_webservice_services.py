"""
Unit tests for organization webservice services.

Tests OrganizationWebserviceService class.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestOrganizationWebserviceServiceStructure:
    """Tests for OrganizationWebserviceService class structure."""

    def test_inherits_from_role_webservice_service(self):
        """Test that OrganizationWebserviceService inherits from RoleWebserviceService."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        assert issubclass(OrganizationWebserviceService, RoleWebserviceService)

    def test_has_accessible_webservices_or_where_method(self):
        """Test that service has _accessible_webservices_or_where method."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
        import inspect

        assert hasattr(OrganizationWebserviceService, "_accessible_webservices_or_where")
        assert inspect.iscoroutinefunction(OrganizationWebserviceService._accessible_webservices_or_where)

    def test_has_user_has_org_role_for_webservice_method(self):
        """Test that service has _user_has_org_role_for_webservice method."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
        import inspect

        assert hasattr(OrganizationWebserviceService, "_user_has_org_role_for_webservice")
        assert inspect.iscoroutinefunction(OrganizationWebserviceService._user_has_org_role_for_webservice)

    def test_has_get_user_access_levels_method(self):
        """Test that service has get_user_access_levels method."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
        import inspect

        assert hasattr(OrganizationWebserviceService, "get_user_access_levels")
        assert inspect.iscoroutinefunction(OrganizationWebserviceService.get_user_access_levels)


class TestOrganizationWebserviceServiceGetUserAccessLevels:
    """Tests for OrganizationWebserviceService.get_user_access_levels method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def mock_webservice(self):
        """Create mock webservice with access levels."""
        webservice = MagicMock()
        webservice.id = "test_webservice"

        # Create mock access levels
        org_role_level = MagicMock()
        org_role_level.id = "ORGANIZATION_ROLE"
        org_role_level.enabled = True

        webservice.access_levels = [org_role_level]
        return webservice

    @pytest.mark.asyncio
    async def test_returns_all_enabled_for_client_owner(self, mock_session, mock_webservice):
        """Test that client owners get all enabled access levels."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        user = {"sub": "user-123"}

        # Mock client_service.user_is_client_owner to return True
        mock_client_service = MagicMock()
        mock_client_service.user_is_client_owner = AsyncMock(return_value=True)

        with patch.object(OrganizationWebserviceService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_client_service

            result = await OrganizationWebserviceService.get_user_access_levels(
                mock_webservice, user, mock_session
            )

        # Should return all enabled access levels
        assert len(result) == 1
        assert result[0].id == "ORGANIZATION_ROLE"

    @pytest.mark.asyncio
    async def test_returns_empty_for_anonymous_user(self, mock_session, mock_webservice):
        """Test that anonymous users get result from parent."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        with patch.object(OrganizationWebserviceService.__bases__[0], 'get_user_access_levels',
                          new_callable=AsyncMock, return_value=[]):
            result = await OrganizationWebserviceService.get_user_access_levels(
                mock_webservice, None, mock_session
            )

        assert result == []


class TestOrganizationWebserviceServiceAccessibleWebservicesOrWhere:
    """Tests for _accessible_webservices_or_where method."""

    def test_method_signature(self):
        """Test _accessible_webservices_or_where method signature."""
        import inspect
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        sig = inspect.signature(OrganizationWebserviceService._accessible_webservices_or_where)

        assert "stmt" in sig.parameters
        assert "user" in sig.parameters
