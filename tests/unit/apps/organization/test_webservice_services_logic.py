"""
Unit tests for organization webservice services logic with mocks.

Tests OrganizationWebserviceService method execution.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestOrganizationWebserviceServiceUserHasOrgRoleForWebservice:
    """Tests for _user_has_org_role_for_webservice method logic."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_returns_true_when_user_is_client_owner(self, mock_session):
        """Test returns True when user is a client owner."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        mock_client_service = MagicMock()
        mock_client_service.user_is_client_owner = AsyncMock(return_value=True)

        with patch.object(OrganizationWebserviceService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_client_service

            result = await OrganizationWebserviceService._user_has_org_role_for_webservice(
                "user-123", "test_webservice", mock_session
            )

        assert result is True
        mock_client_service.user_is_client_owner.assert_called_once_with("user-123", mock_session)


class TestOrganizationWebserviceServiceGetUserAccessLevels:
    """Tests for get_user_access_levels method logic."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.fixture
    def mock_webservice(self):
        """Create mock webservice."""
        ws = MagicMock()
        ws.id = "test_ws"

        # Create access levels
        org_role_level = MagicMock()
        org_role_level.id = "ORGANIZATION_ROLE"
        org_role_level.enabled = True

        other_level = MagicMock()
        other_level.id = "OTHER"
        other_level.enabled = True

        ws.access_levels = [org_role_level, other_level]
        return ws

    @pytest.mark.asyncio
    async def test_adds_org_role_when_user_has_org_role(self, mock_session, mock_webservice):
        """Test adds ORGANIZATION_ROLE access level when user has org role."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        user = {"sub": "user-123"}

        mock_client_service = MagicMock()
        mock_client_service.user_is_client_owner = AsyncMock(return_value=False)

        with patch.object(OrganizationWebserviceService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_client_service

            with patch.object(OrganizationWebserviceService.__bases__[0], 'get_user_access_levels',
                              new_callable=AsyncMock, return_value=[]):
                with patch.object(OrganizationWebserviceService, '_user_has_org_role_for_webservice',
                                  new_callable=AsyncMock, return_value=True):
                    result = await OrganizationWebserviceService.get_user_access_levels(
                        mock_webservice, user, mock_session
                    )

        # Should include ORGANIZATION_ROLE
        access_level_ids = [al.id for al in result]
        assert "ORGANIZATION_ROLE" in access_level_ids

    @pytest.mark.asyncio
    async def test_skips_disabled_org_role_access_level(self, mock_session):
        """Test skips disabled ORGANIZATION_ROLE access level."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        user = {"sub": "user-123"}

        # Create webservice with disabled ORGANIZATION_ROLE
        mock_ws = MagicMock()
        mock_ws.id = "test_ws"

        disabled_level = MagicMock()
        disabled_level.id = "ORGANIZATION_ROLE"
        disabled_level.enabled = False

        mock_ws.access_levels = [disabled_level]

        mock_client_service = MagicMock()
        mock_client_service.user_is_client_owner = AsyncMock(return_value=False)

        with patch.object(OrganizationWebserviceService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_client_service

            with patch.object(OrganizationWebserviceService.__bases__[0], 'get_user_access_levels',
                              new_callable=AsyncMock, return_value=[]):
                with patch.object(OrganizationWebserviceService, '_user_has_org_role_for_webservice',
                                  new_callable=AsyncMock, return_value=True):
                    result = await OrganizationWebserviceService.get_user_access_levels(
                        mock_ws, user, mock_session
                    )

        # Should not include disabled access level
        assert len(result) == 0


class TestOrganizationWebserviceServiceAccessibleWebservicesOrWhere:
    """Tests for _accessible_webservices_or_where method logic."""

    @pytest.mark.asyncio
    async def test_skips_condition_for_super_user(self):
        """Test skips organization condition for super users."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        mock_stmt = MagicMock()
        user = {"sub": "user-123", "is_super_user": True}

        parent_where = MagicMock()

        with patch.object(OrganizationWebserviceService.__bases__[0], '_accessible_webservices_or_where',
                          new_callable=AsyncMock, return_value=(mock_stmt, parent_where)):
            result_stmt, result_where = await OrganizationWebserviceService._accessible_webservices_or_where(
                mock_stmt, user
            )

        # Should return parent's where unchanged
        assert result_where == parent_where

    @pytest.mark.asyncio
    async def test_skips_condition_for_anonymous_user(self):
        """Test skips organization condition for anonymous users."""
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        mock_stmt = MagicMock()

        with patch.object(OrganizationWebserviceService.__bases__[0], '_accessible_webservices_or_where',
                          new_callable=AsyncMock, return_value=(mock_stmt, None)):
            result_stmt, result_where = await OrganizationWebserviceService._accessible_webservices_or_where(
                mock_stmt, None
            )

        # Should return None where for anonymous
        assert result_where is None


class TestOrganizationWebserviceServiceMethodSignatures:
    """Tests for method signatures."""

    def test_user_has_org_role_for_webservice_signature(self):
        """Test _user_has_org_role_for_webservice method signature."""
        import inspect
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        sig = inspect.signature(OrganizationWebserviceService._user_has_org_role_for_webservice)
        assert "user_id" in sig.parameters
        assert "webservice_id" in sig.parameters
        assert "session" in sig.parameters

    def test_accessible_webservices_or_where_signature(self):
        """Test _accessible_webservices_or_where method signature."""
        import inspect
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService

        sig = inspect.signature(OrganizationWebserviceService._accessible_webservices_or_where)
        assert "stmt" in sig.parameters
        assert "user" in sig.parameters
