"""
Test the MockAppManager functionality.

This test validates that the mocking strategy works correctly
with real lys framework components.
"""

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity
from lys.core.services import EntityService
from tests.mocks import MockAppManager, configure_classes_for_testing


class TestEntity(Entity):
    """Test entity for validation."""

    __tablename__ = "test_entities"
    __abstract__ = False

    name: Mapped[str] = mapped_column(String(100))


class TestService(EntityService[TestEntity]):
    """Test service for validation."""

    pass


class TestMockAppManager:
    """Test suite for MockAppManager functionality."""

    def test_can_create_mock_app_manager(self):
        """Test that MockAppManager can be instantiated."""
        mock_app = MockAppManager()
        assert mock_app is not None
        assert hasattr(mock_app, "get_entity")
        assert hasattr(mock_app, "get_service")
        assert hasattr(mock_app, "register_entity")
        assert hasattr(mock_app, "register_service")

    def test_can_register_entity(self):
        """Test that entities can be registered in MockAppManager."""
        mock_app = MockAppManager()
        mock_app.register_entity("test_entities", TestEntity)

        retrieved_entity = mock_app.get_entity("test_entities")
        assert retrieved_entity == TestEntity

    def test_can_register_service(self):
        """Test that services can be registered in MockAppManager."""
        mock_app = MockAppManager()
        mock_app.register_service("test_entities", TestService)

        retrieved_service = mock_app.get_service("test_entities")
        assert retrieved_service == TestService

    def test_get_entity_raises_on_missing(self):
        """Test that get_entity raises KeyError for unregistered entities."""
        mock_app = MockAppManager()

        with pytest.raises(KeyError) as exc_info:
            mock_app.get_entity("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not registered" in str(exc_info.value)

    def test_get_service_raises_on_missing(self):
        """Test that get_service raises KeyError for unregistered services."""
        mock_app = MockAppManager()

        with pytest.raises(KeyError) as exc_info:
            mock_app.get_service("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not registered" in str(exc_info.value)

    def test_can_chain_registrations(self):
        """Test that registration methods can be chained."""
        mock_app = MockAppManager()

        result = (
            mock_app
            .register_entity("test_entities", TestEntity)
            .register_service("test_entities", TestService)
        )

        assert result == mock_app
        assert mock_app.get_entity("test_entities") == TestEntity
        assert mock_app.get_service("test_entities") == TestService

    def test_configure_service_to_use_mock(self):
        """
        Test that a service can be configured to use MockAppManager.

        This is the key integration test - validates that the
        configure_app_manager_for_testing() method works correctly.
        """
        # Setup mock
        mock_app = MockAppManager()
        mock_app.register_entity("test_entities", TestEntity)
        mock_app.register_service("test_entities", TestService)

        # Configure service to use mock
        TestService.configure_app_manager_for_testing(mock_app)

        # Verify service uses the mock
        assert TestService.app_manager == mock_app
        assert TestService.entity_class == TestEntity

    def test_configure_multiple_classes(self):
        """Test configure_classes_for_testing utility."""
        mock_app = MockAppManager()
        mock_app.register_entity("test_entities", TestEntity)
        mock_app.register_service("test_entities", TestService)

        # Configure using utility
        configure_classes_for_testing(mock_app, TestService)

        # Verify configuration
        assert TestService.app_manager == mock_app

    def test_mock_database_manager_exists(self):
        """Test that MockAppManager has a database property."""
        mock_app = MockAppManager()

        assert hasattr(mock_app, "database")
        assert hasattr(mock_app.database, "get_session")
        assert hasattr(mock_app.database, "execute_parallel")

    def test_mock_settings_exists(self):
        """Test that MockAppManager has a settings property."""
        mock_app = MockAppManager()

        assert hasattr(mock_app, "settings")
        assert hasattr(mock_app.settings, "database")

    @pytest.mark.asyncio
    async def test_mock_database_execute_parallel(self):
        """Test that mock database execute_parallel works."""
        mock_app = MockAppManager()

        async def query1(session):
            return "result1"

        async def query2(session):
            return "result2"

        results = await mock_app.database.execute_parallel(query1, query2)

        assert results == ["result1", "result2"]
