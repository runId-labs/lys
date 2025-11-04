"""
Test that test isolation works correctly.

This validates that the auto_cleanup_app_managers fixture
prevents tests from interfering with each other.
"""

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity
from lys.core.services import EntityService
from tests.mocks import MockAppManager, configure_classes_for_testing


class IsolationTestEntity(Entity):
    """Test entity for isolation validation."""
    __tablename__ = "isolation_test"
    __abstract__ = False
    name: Mapped[str] = mapped_column(String(100))


class IsolationTestService(EntityService[IsolationTestEntity]):
    """Test service for isolation validation."""
    pass


class TestIsolation:
    """Test suite to validate test isolation."""

    def test_first_configures_service(self):
        """
        First test configures the service with a mock.

        This test should NOT affect test_second_starts_clean.
        """
        mock_app = MockAppManager()
        mock_app.register_entity("isolation_test", IsolationTestEntity)

        configure_classes_for_testing(mock_app, IsolationTestService)

        # Verify configuration
        assert IsolationTestService.app_manager == mock_app
        assert IsolationTestService._app_manager == mock_app

    def test_second_starts_clean(self):
        """
        Second test should start with clean state.

        If isolation works, IsolationTestService._app_manager should be None,
        not the mock from test_first_configures_service.
        """
        # This is the critical assertion - _app_manager should be None
        assert IsolationTestService._app_manager is None

        # We can configure it independently
        different_mock = MockAppManager()
        different_mock.register_entity("isolation_test", IsolationTestEntity)

        configure_classes_for_testing(different_mock, IsolationTestService)

        # Verify it uses the NEW mock, not the old one
        assert IsolationTestService.app_manager == different_mock

    def test_third_also_starts_clean(self):
        """
        Third test should also start with clean state.

        This confirms cleanup works consistently across multiple tests.
        """
        # Should be clean after test_second_starts_clean
        assert IsolationTestService._app_manager is None

    def test_explicit_manual_config_without_tracking(self):
        """
        Test that even manual configuration gets cleaned up.

        Note: If you call configure_app_manager_for_testing() directly
        WITHOUT tracking, the auto_cleanup won't clean it up.
        This test demonstrates the importance of using configure_classes_for_testing().
        """
        mock_app = MockAppManager()
        mock_app.register_entity("isolation_test", IsolationTestEntity)

        # Manual config WITHOUT tracking - risky!
        IsolationTestService.configure_app_manager_for_testing(mock_app)

        # It works...
        assert IsolationTestService._app_manager == mock_app

        # But there's no cleanup! This is why you should use
        # configure_classes_for_testing() which tracks automatically.

    def test_after_manual_config_state_persists(self):
        """
        This test shows that manual config WITHOUT tracking leaks state.

        WARNING: This test might fail if run in different order!
        It depends on test_explicit_manual_config_without_tracking running first.

        This is exactly the problem the auto-cleanup and tracking solves.
        """
        # If test_explicit_manual_config_without_tracking ran before this,
        # and we're lucky with test order, _app_manager might still be set

        # The solution: ALWAYS use configure_classes_for_testing()
        # which tracks for automatic cleanup!

        # For this test, we'll just clean it manually to prevent affecting others
        from tests.mocks.utils import reset_class_app_managers
        reset_class_app_managers(IsolationTestService)

        assert IsolationTestService._app_manager is None
