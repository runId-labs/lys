"""
Unit tests for user_role RoleWebserviceService.

Tests the webservice service with role-based access.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRoleWebserviceServiceGetUserAccessLevels:
    """Tests for RoleWebserviceService.get_user_access_levels method."""

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
        role_access_level = MagicMock()
        role_access_level.id = "ROLE"
        role_access_level.enabled = True

        webservice.access_levels = [role_access_level]
        return webservice

    @pytest.mark.asyncio
    async def test_returns_empty_for_anonymous_user(self, mock_session, mock_webservice):
        """Test that anonymous users get empty access levels."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        # Mock parent method
        with patch.object(RoleWebserviceService.__bases__[0], 'get_user_access_levels',
                          new_callable=AsyncMock, return_value=[]):
            result = await RoleWebserviceService.get_user_access_levels(
                mock_webservice, None, mock_session
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_adds_role_access_level_when_user_has_role(self, mock_session, mock_webservice):
        """Test that ROLE access level is added when user has matching role."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        user = {"sub": "user-123"}

        with patch.object(RoleWebserviceService.__bases__[0], 'get_user_access_levels',
                          new_callable=AsyncMock, return_value=[]):
            with patch.object(RoleWebserviceService, '_user_has_role_for_webservice',
                              new_callable=AsyncMock, return_value=True):
                result = await RoleWebserviceService.get_user_access_levels(
                    mock_webservice, user, mock_session
                )

        # Should include the ROLE access level
        assert len(result) == 1
        assert result[0].id == "ROLE"

    @pytest.mark.asyncio
    async def test_skips_disabled_access_levels(self, mock_session):
        """Test that disabled access levels are skipped."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        # Create webservice with disabled ROLE access level
        webservice = MagicMock()
        webservice.id = "test_webservice"

        role_access_level = MagicMock()
        role_access_level.id = "ROLE"
        role_access_level.enabled = False  # Disabled

        webservice.access_levels = [role_access_level]

        user = {"sub": "user-123"}

        with patch.object(RoleWebserviceService.__bases__[0], 'get_user_access_levels',
                          new_callable=AsyncMock, return_value=[]):
            with patch.object(RoleWebserviceService, '_user_has_role_for_webservice',
                              new_callable=AsyncMock, return_value=True):
                result = await RoleWebserviceService.get_user_access_levels(
                    webservice, user, mock_session
                )

        # Disabled access level should not be added
        assert result == []


class TestRoleWebserviceServiceAccessibleWebservices:
    """Tests for RoleWebserviceService.accessible_webservices method."""

    def test_method_exists(self):
        """Test that accessible_webservices method exists."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        assert hasattr(RoleWebserviceService, 'accessible_webservices')

    def test_method_is_async(self):
        """Test that accessible_webservices is an async method."""
        import inspect
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        assert inspect.iscoroutinefunction(RoleWebserviceService.accessible_webservices)

    def test_method_accepts_role_code_parameter(self):
        """Test that method accepts role_code parameter."""
        import inspect
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        sig = inspect.signature(RoleWebserviceService.accessible_webservices)
        assert 'role_code' in sig.parameters


class TestRoleWebserviceServiceInheritance:
    """Tests for RoleWebserviceService class structure."""

    def test_inherits_from_auth_webservice_service(self):
        """Test that RoleWebserviceService inherits from AuthWebserviceService."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService
        from lys.apps.user_auth.modules.webservice.services import AuthWebserviceService

        assert issubclass(RoleWebserviceService, AuthWebserviceService)

    def test_has_accessible_webservices_or_where_method(self):
        """Test that service has _accessible_webservices_or_where method."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        assert hasattr(RoleWebserviceService, '_accessible_webservices_or_where')

    def test_has_user_has_role_for_webservice_method(self):
        """Test that service has _user_has_role_for_webservice method."""
        from lys.apps.user_role.modules.webservice.services import RoleWebserviceService

        assert hasattr(RoleWebserviceService, '_user_has_role_for_webservice')


class TestRoleServiceStructure:
    """Tests for RoleService structure."""

    def test_role_service_inherits_entity_service(self):
        """Test that RoleService inherits from EntityService."""
        from lys.apps.user_role.modules.role.services import RoleService
        from lys.core.services import EntityService

        assert issubclass(RoleService, EntityService)
