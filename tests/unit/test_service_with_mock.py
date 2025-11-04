"""
Test real lys services using MockAppManager.

This test validates that the mocking strategy works with actual
services from the lys framework, not just test entities.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy import select

from lys.apps.base.modules.language.entities import Language
from lys.apps.base.modules.language.services import LanguageService
from tests.mocks import MockAppManager, configure_classes_for_testing
from tests.mocks.utils import track_configured_class


class TestLanguageServiceWithMock:
    """Test LanguageService using MockAppManager."""

    def test_service_can_access_entity_class_via_mock(self):
        """
        Test that a service can access its entity class through MockAppManager.

        This validates the critical pattern:
        service.entity_class -> app_manager.get_entity(service_name)
        """
        # Setup mock
        mock_app = MockAppManager()
        mock_app.register_entity("language", Language)

        # Configure service (with automatic cleanup tracking)
        configure_classes_for_testing(mock_app, LanguageService)

        # Test - entity_class property should work
        entity_class = LanguageService.entity_class
        assert entity_class == Language

    @pytest.mark.skip(reason="SQLAlchemy CRUD methods require real database - use integration tests instead")
    @pytest.mark.asyncio
    async def test_service_get_by_id_with_mock_session(self):
        """
        Test LanguageService.get_by_id with mocked database session.

        NOTE: This test is skipped because SQLAlchemy CRUD methods (get_by_id, create, etc.)
        require a properly configured database context. These should be tested as
        integration tests with a real SQLite in-memory database, not as unit tests.

        The mock strategy works for:
        - Accessing entity_class property
        - Testing business logic that doesn't use SQLAlchemy queries
        - Testing service methods that delegate to other services

        For CRUD testing, see: tests/integration/test_services.py
        """
        pass

    @pytest.mark.skip(reason="SQLAlchemy entity instantiation requires real database context - use integration tests")
    @pytest.mark.asyncio
    async def test_service_create_with_mock_session(self):
        """
        Test LanguageService.create with mocked database session.

        NOTE: This test is skipped because SQLAlchemy entities cannot be instantiated
        without a proper database session and mapping context.

        For CRUD testing, use integration tests with real SQLite database.
        See: tests/integration/test_services.py
        """
        pass

    def test_multiple_services_share_mock(self):
        """
        Test that multiple services can share the same MockAppManager.

        This is important for testing service interactions.
        """
        from lys.apps.base.modules.access_level.entities import AccessLevel
        from lys.apps.base.modules.access_level.services import AccessLevelService

        # Setup mock with multiple entities
        mock_app = MockAppManager()
        mock_app.register_entity("language", Language)
        mock_app.register_entity("access_level", AccessLevel)

        # Configure both services (with automatic cleanup tracking)
        configure_classes_for_testing(mock_app, LanguageService, AccessLevelService)

        # Verify both services use the same mock
        assert LanguageService.app_manager == mock_app
        assert AccessLevelService.app_manager == mock_app

        # Verify each service can access its entity
        assert LanguageService.entity_class == Language
        assert AccessLevelService.entity_class == AccessLevel

    @pytest.mark.asyncio
    async def test_service_with_dependency_on_another_service(self):
        """
        Test a service that calls another service internally.

        This validates that cross-service calls work with mocking.
        """
        # This is a more advanced scenario - we'll create a simple example
        # In real code, UserService might call EmailService, etc.

        # Setup mock with both entities
        mock_app = MockAppManager()
        mock_app.register_entity("language", Language)
        mock_app.register_service("language", LanguageService)

        # Configure service (with automatic cleanup tracking)
        configure_classes_for_testing(mock_app, LanguageService)

        # Now if LanguageService internally called:
        # other_service = cls.app_manager.get_service("language")
        # It would get LanguageService back

        retrieved_service = LanguageService.app_manager.get_service("language")
        assert retrieved_service == LanguageService

    def test_cleanup_after_test(self):
        """
        Test manual cleanup functionality.

        Note: With the auto_cleanup_app_managers fixture, cleanup happens
        automatically, but this test validates the manual cleanup function
        still works correctly.
        """
        from tests.mocks.utils import reset_class_app_managers

        # Setup
        mock_app = MockAppManager()
        mock_app.register_entity("language", Language)
        LanguageService.configure_app_manager_for_testing(mock_app)

        # Verify configured
        assert LanguageService._app_manager == mock_app

        # Manual cleanup (normally happens automatically)
        reset_class_app_managers(LanguageService)

        # Verify reset - should return to None
        assert LanguageService._app_manager is None

        # Note: The auto_cleanup fixture will try to clean up again at test end,
        # but that's safe - resetting None to None has no effect
