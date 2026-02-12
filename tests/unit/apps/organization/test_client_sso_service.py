"""
Unit tests for ClientService.create_client_with_sso_owner().

Tests cover:
- Full SSO client creation flow (consume session, create user, create client, create link)
- SSO name fallbacks (use SSO data when form fields are empty)
- Email validated at creation from SSO provider

Test approach: Unit (mocked app_manager, services, and session)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from lys.apps.organization.modules.client.services import ClientService
from lys.core.errors import LysError

from tests.mocks.utils import configure_classes_for_testing
from tests.mocks.app_manager import MockAppManager


@pytest.fixture
def client_app_manager():
    """Create a mock app_manager configured for client SSO tests."""
    mock_app = MockAppManager()

    mock_settings = MagicMock()
    mock_settings.front_url = "https://app.example.com"
    mock_app.settings = mock_settings

    # Mock SSO auth service
    mock_sso_auth_service = MagicMock()
    mock_sso_auth_service.consume_sso_session = AsyncMock(return_value={
        "provider": "microsoft",
        "email": "sso-user@example.com",
        "first_name": "SSO-First",
        "last_name": "SSO-Last",
        "external_user_id": "ext-sso-001",
    })
    mock_app.register_service("sso_auth", mock_sso_auth_service)

    # Mock user service
    mock_owner_user = MagicMock()
    mock_owner_user.id = "owner-user-id"
    mock_owner_user.email_address = MagicMock()
    mock_owner_user.email_address.validated_at = None

    mock_user_service = MagicMock()
    mock_user_service.create_user = AsyncMock(return_value=mock_owner_user)
    mock_app.register_service("user", mock_user_service)

    # Mock SSO link service
    mock_sso_link_service = MagicMock()
    mock_sso_link_service.create_link = AsyncMock()
    mock_app.register_service("user_sso_link", mock_sso_link_service)

    # Mock entity_class (Client)
    mock_client = MagicMock()
    mock_client.id = "client-id"
    ClientService.entity_class = MagicMock(return_value=mock_client)

    configure_classes_for_testing(mock_app, ClientService)

    return mock_app


class TestCreateClientWithSSOOwner:
    """Tests for ClientService.create_client_with_sso_owner()."""

    @pytest.mark.asyncio
    async def test_full_flow_success(self, client_app_manager):
        """Full SSO client creation: consume session, create user, create client, create link."""
        session = AsyncMock()

        client = await ClientService.create_client_with_sso_owner(
            session=session,
            client_name="My Company",
            sso_token="sso-token-123",
            language_id="en",
        )

        # Verify SSO session consumed
        sso_auth = client_app_manager.get_service("sso_auth")
        sso_auth.consume_sso_session.assert_called_once_with("sso-token-123")

        # Verify user created with no password
        user_service = client_app_manager.get_service("user")
        user_service.create_user.assert_called_once()
        call_kwargs = user_service.create_user.call_args[1]
        assert call_kwargs["password"] is None
        assert call_kwargs["email"] == "sso-user@example.com"
        assert call_kwargs["send_verification_email"] is False

        # Verify client entity created
        assert client is not None

        # Verify SSO link created
        sso_link = client_app_manager.get_service("user_sso_link")
        sso_link.create_link.assert_called_once_with(
            user_id="owner-user-id",
            provider="microsoft",
            external_user_id="ext-sso-001",
            external_email="sso-user@example.com",
            session=session,
        )

    @pytest.mark.asyncio
    async def test_uses_sso_names_as_fallback(self, client_app_manager):
        """When first_name/last_name not provided, SSO data is used."""
        session = AsyncMock()

        await ClientService.create_client_with_sso_owner(
            session=session,
            client_name="My Company",
            sso_token="sso-token-123",
            language_id="en",
            first_name=None,
            last_name=None,
        )

        user_service = client_app_manager.get_service("user")
        call_kwargs = user_service.create_user.call_args[1]
        assert call_kwargs["first_name"] == "SSO-First"
        assert call_kwargs["last_name"] == "SSO-Last"

    @pytest.mark.asyncio
    async def test_explicit_names_override_sso(self, client_app_manager):
        """Explicitly provided names take precedence over SSO data."""
        session = AsyncMock()

        await ClientService.create_client_with_sso_owner(
            session=session,
            client_name="My Company",
            sso_token="sso-token-123",
            language_id="en",
            first_name="Custom-First",
            last_name="Custom-Last",
        )

        user_service = client_app_manager.get_service("user")
        call_kwargs = user_service.create_user.call_args[1]
        assert call_kwargs["first_name"] == "Custom-First"
        assert call_kwargs["last_name"] == "Custom-Last"

    @pytest.mark.asyncio
    async def test_email_marked_as_validated(self, client_app_manager):
        """Owner email_address.validated_at is set (provider verified the email)."""
        session = AsyncMock()

        await ClientService.create_client_with_sso_owner(
            session=session,
            client_name="My Company",
            sso_token="sso-token-123",
            language_id="en",
        )

        user_service = client_app_manager.get_service("user")
        mock_owner = user_service.create_user.return_value
        assert mock_owner.email_address.validated_at is not None

    @pytest.mark.asyncio
    async def test_owner_associated_with_client(self, client_app_manager):
        """Owner user.client_id is set to the created client ID."""
        session = AsyncMock()

        await ClientService.create_client_with_sso_owner(
            session=session,
            client_name="My Company",
            sso_token="sso-token-123",
            language_id="en",
        )

        user_service = client_app_manager.get_service("user")
        mock_owner = user_service.create_user.return_value
        assert mock_owner.client_id == "client-id"
