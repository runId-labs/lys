"""
Unit tests for organization auth services logic with mocks.

Tests the actual method execution with mocked dependencies.
Note: Some methods use SQLAlchemy select() which can't accept MagicMock,
so those are tested at integration level.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestOrganizationAuthServiceGetUserOrganizations:
    """Tests for _get_user_organizations method logic."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_combines_owner_and_role_webservices(self, mock_session):
        """Test that owner and role webservices are combined."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        owner_orgs = {
            "client-1": {"level": "client", "webservices": ["ws1", "ws2"]}
        }
        role_orgs = {
            "client-2": {"level": "client", "webservices": ["ws3"]}
        }

        with patch.object(OrganizationAuthService, '_get_owner_webservices',
                          new_callable=AsyncMock, return_value=owner_orgs):
            with patch.object(OrganizationAuthService, '_get_client_user_role_webservices',
                              new_callable=AsyncMock, return_value=role_orgs):
                result = await OrganizationAuthService._get_user_organizations("user-123", mock_session)

        assert "client-1" in result
        assert "client-2" in result
        assert result["client-1"]["webservices"] == ["ws1", "ws2"]
        assert result["client-2"]["webservices"] == ["ws3"]

    @pytest.mark.asyncio
    async def test_owner_takes_precedence_over_role(self, mock_session):
        """Test that owner webservices take precedence when user has both."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        # Same org with different webservices
        owner_orgs = {
            "client-1": {"level": "client", "webservices": ["ws1", "ws2", "ws3"]}
        }
        role_orgs = {
            "client-1": {"level": "client", "webservices": ["ws1"]}  # Subset
        }

        with patch.object(OrganizationAuthService, '_get_owner_webservices',
                          new_callable=AsyncMock, return_value=owner_orgs):
            with patch.object(OrganizationAuthService, '_get_client_user_role_webservices',
                              new_callable=AsyncMock, return_value=role_orgs):
                result = await OrganizationAuthService._get_user_organizations("user-123", mock_session)

        # Owner webservices should win
        assert result["client-1"]["webservices"] == ["ws1", "ws2", "ws3"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_orgs(self, mock_session):
        """Test returns empty dict when user has no organizations."""
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        with patch.object(OrganizationAuthService, '_get_owner_webservices',
                          new_callable=AsyncMock, return_value={}):
            with patch.object(OrganizationAuthService, '_get_client_user_role_webservices',
                              new_callable=AsyncMock, return_value={}):
                result = await OrganizationAuthService._get_user_organizations("user-123", mock_session)

        assert result == {}


class TestOrganizationAuthServiceMethodSignatures:
    """Tests for method signatures and structure."""

    def test_get_owner_webservices_signature(self):
        """Test _get_owner_webservices method signature."""
        import inspect
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        sig = inspect.signature(OrganizationAuthService._get_owner_webservices)
        assert "user_id" in sig.parameters
        assert "session" in sig.parameters

    def test_get_client_user_role_webservices_signature(self):
        """Test _get_client_user_role_webservices method signature."""
        import inspect
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        sig = inspect.signature(OrganizationAuthService._get_client_user_role_webservices)
        assert "user_id" in sig.parameters
        assert "session" in sig.parameters

    def test_get_user_organizations_signature(self):
        """Test _get_user_organizations method signature."""
        import inspect
        from lys.apps.organization.modules.auth.services import OrganizationAuthService

        sig = inspect.signature(OrganizationAuthService._get_user_organizations)
        assert "user_id" in sig.parameters
        assert "session" in sig.parameters
