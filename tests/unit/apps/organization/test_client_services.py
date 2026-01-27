"""
Unit tests for organization ClientService.

Tests the client service business logic.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestClientServiceStructure:
    """Tests for ClientService class structure."""

    def test_inherits_from_entity_service(self):
        """Test that ClientService inherits from EntityService."""
        from lys.apps.organization.modules.client.services import ClientService
        from lys.core.services import EntityService

        assert issubclass(ClientService, EntityService)

    def test_has_create_client_with_owner_method(self):
        """Test that ClientService has create_client_with_owner method."""
        from lys.apps.organization.modules.client.services import ClientService
        import inspect

        assert hasattr(ClientService, "create_client_with_owner")
        assert inspect.iscoroutinefunction(ClientService.create_client_with_owner)

    def test_has_user_is_client_owner_method(self):
        """Test that ClientService has user_is_client_owner method."""
        from lys.apps.organization.modules.client.services import ClientService
        import inspect

        assert hasattr(ClientService, "user_is_client_owner")
        assert inspect.iscoroutinefunction(ClientService.user_is_client_owner)


class TestClientServiceCreateClientWithOwner:
    """Tests for ClientService.create_client_with_owner method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    def test_method_signature(self):
        """Test create_client_with_owner method signature."""
        import inspect
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


class TestClientServiceUserIsClientOwner:
    """Tests for ClientService.user_is_client_owner method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session

    def test_method_signature(self):
        """Test user_is_client_owner method signature."""
        import inspect
        from lys.apps.organization.modules.client.services import ClientService

        sig = inspect.signature(ClientService.user_is_client_owner)

        assert "user_id" in sig.parameters
        assert "session" in sig.parameters
