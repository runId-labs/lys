"""
Unit tests for organization ClientService logic with mocks.

Tests the actual method execution with mocked dependencies.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import pytest
import inspect
from unittest.mock import MagicMock, AsyncMock, patch


class TestClientServiceUserIsClientOwnerSignature:
    """Tests for user_is_client_owner method signature."""

    def test_method_is_async(self):
        """Test that user_is_client_owner is async."""
        from lys.apps.organization.modules.client.services import ClientService

        assert inspect.iscoroutinefunction(ClientService.user_is_client_owner)

    def test_method_signature(self):
        """Test user_is_client_owner method signature."""
        from lys.apps.organization.modules.client.services import ClientService

        sig = inspect.signature(ClientService.user_is_client_owner)
        assert "user_id" in sig.parameters
        assert "session" in sig.parameters


class TestClientServiceCreateClientWithOwner:
    """Tests for ClientService.create_client_with_owner method logic."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_creates_user_and_client(self, mock_session):
        """Test that method creates user and client."""
        from lys.apps.organization.modules.client.services import ClientService

        # Mock user service
        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_user_service = MagicMock()
        mock_user_service.create_user = AsyncMock(return_value=mock_user)

        # Mock client entity class
        mock_client = MagicMock()
        mock_client.id = "client-456"
        mock_client_class = MagicMock(return_value=mock_client)

        with patch.object(ClientService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_user_service

            with patch.object(ClientService, 'entity_class', mock_client_class):
                result = await ClientService.create_client_with_owner(
                    session=mock_session,
                    client_name="Test Client",
                    email="test@example.com",
                    password="password123",
                    language_id="en"
                )

        # Verify user was created
        mock_user_service.create_user.assert_called_once()

        # Verify client was created with owner_id
        mock_client_class.assert_called_once_with(
            name="Test Client",
            owner_id="user-123"
        )

        # Verify session.add was called for client
        mock_session.add.assert_called_once_with(mock_client)

        # Verify owner user's client_id is set
        assert mock_user.client_id == "client-456"

    @pytest.mark.asyncio
    async def test_passes_optional_parameters(self, mock_session):
        """Test that optional parameters are passed to user creation."""
        from lys.apps.organization.modules.client.services import ClientService

        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_user_service = MagicMock()
        mock_user_service.create_user = AsyncMock(return_value=mock_user)

        mock_client = MagicMock()
        mock_client.id = "client-456"
        mock_client_class = MagicMock(return_value=mock_client)

        with patch.object(ClientService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_user_service

            with patch.object(ClientService, 'entity_class', mock_client_class):
                await ClientService.create_client_with_owner(
                    session=mock_session,
                    client_name="Test Client",
                    email="test@example.com",
                    password="password123",
                    language_id="en",
                    send_verification_email=False,
                    first_name="John",
                    last_name="Doe",
                    gender_id="MALE"
                )

        # Verify optional parameters were passed
        call_kwargs = mock_user_service.create_user.call_args.kwargs
        assert call_kwargs["first_name"] == "John"
        assert call_kwargs["last_name"] == "Doe"
        assert call_kwargs["gender_id"] == "MALE"
        assert call_kwargs["send_verification_email"] is False


class TestClientServiceCreateClientWithOwnerSignature:
    """Tests for create_client_with_owner method signature."""

    def test_method_is_async(self):
        """Test that create_client_with_owner is async."""
        from lys.apps.organization.modules.client.services import ClientService

        assert inspect.iscoroutinefunction(ClientService.create_client_with_owner)

    def test_method_signature(self):
        """Test create_client_with_owner method signature."""
        from lys.apps.organization.modules.client.services import ClientService

        sig = inspect.signature(ClientService.create_client_with_owner)
        assert "session" in sig.parameters
        assert "client_name" in sig.parameters
        assert "email" in sig.parameters
        assert "password" in sig.parameters
        assert "language_id" in sig.parameters
        assert "send_verification_email" in sig.parameters
        assert "background_tasks" in sig.parameters
        assert "first_name" in sig.parameters
        assert "last_name" in sig.parameters
        assert "gender_id" in sig.parameters
