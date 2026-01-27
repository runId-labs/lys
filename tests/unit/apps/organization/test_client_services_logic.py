"""
Unit tests for organization ClientService logic with mocks.

Tests the actual method execution with mocked dependencies.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestClientServiceUserIsClientOwnerSignature:
    """Tests for user_is_client_owner method signature."""

    def test_method_is_async(self):
        """Test that user_is_client_owner is async."""
        import inspect
        from lys.apps.organization.modules.client.services import ClientService

        assert inspect.iscoroutinefunction(ClientService.user_is_client_owner)

    def test_method_signature(self):
        """Test user_is_client_owner method signature."""
        import inspect
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
    async def test_creates_user_client_and_client_user(self, mock_session):
        """Test that method creates user, client, and client_user."""
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

        # Mock client_user entity class
        mock_client_user = MagicMock()
        mock_client_user_class = MagicMock(return_value=mock_client_user)

        with patch.object(ClientService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_user_service
            mock_app_manager.get_entity.return_value = mock_client_user_class

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

        # Verify session.add was called (for client and client_user)
        assert mock_session.add.call_count >= 2

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

        mock_client_user_class = MagicMock()

        with patch.object(ClientService, 'app_manager') as mock_app_manager:
            mock_app_manager.get_service.return_value = mock_user_service
            mock_app_manager.get_entity.return_value = mock_client_user_class

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
