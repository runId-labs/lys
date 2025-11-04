"""
Pytest configuration and shared fixtures for lys framework tests.

This file contains:
- Test configuration
- Shared fixtures for app_manager, database, etc.
- Common test utilities

Note: This is a work in progress as part of the testing strategy development.
See docs/todos/testing/STATUS.md for current status.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from tests.mocks.app_manager import MockAppManager
from tests.mocks.utils import (
    get_tracked_classes,
    clear_tracked_classes,
    reset_class_app_managers,
    track_configured_class
)

# Import integration test fixtures
from tests.fixtures.database import (
    test_app_manager,
    db_session,
    db_session_commit
)


@pytest.fixture(scope="function", autouse=True)
def isolate_sqlalchemy_registry():
    """
    Isolate SQLAlchemy's declarative registry between tests.

    The real issue is NOT the LysAppRegister singleton itself, but SQLAlchemy's
    Base metadata registry that maintains a global class lookup table. When multiple
    test modules load the same entities, SQLAlchemy complains about "replaced in
    string-lookup table" and behavior becomes unpredictable.

    This fixture clears ONLY the SQLAlchemy class registry after each test, while
    leaving LysAppRegister intact. This allows:
    - Each test to register entities fresh in SQLAlchemy
    - LysAppRegister to maintain state within a test file (needed for AppManager)
    - Different test files to not conflict with each other

    Why this works:
    - SQLAlchemy Base.registry._class_registry is the actual source of conflicts
    - LysAppRegister can accumulate state within a module without issues
    - Each test gets a clean SQLAlchemy slate but shares LysAppRegister within module
    """
    yield

    # After each test - clear SQLAlchemy's class registry
    try:
        from lys.core.managers.database import Base
        if hasattr(Base, 'registry') and hasattr(Base.registry, '_class_registry'):
            # Clear the class name lookup but keep metadata
            Base.registry._class_registry.clear()
    except Exception:
        # If Base isn't available or structure changed, silently continue
        pass


@pytest.fixture(autouse=True)
def auto_cleanup_app_managers():
    """
    Automatically cleanup all configured app_managers after each test.

    This fixture runs automatically for every test (autouse=True) and ensures
    that no test pollutes another test's state.

    How it works:
    1. Before test: clear the tracking list
    2. Test runs: classes get configured via configure_classes_for_testing()
    3. After test: reset all configured classes to None

    This prevents test isolation issues where one test's mock configuration
    affects another test.
    """
    # Before test - clear tracking
    clear_tracked_classes()

    yield

    # After test - cleanup all configured classes
    configured_classes = get_tracked_classes()
    if configured_classes:
        reset_class_app_managers(*configured_classes)


@pytest.fixture
def mock_app_manager():
    """
    Basic mock app_manager for unit tests.

    Returns a MockAppManager instance that can be used to register
    entities and services for testing.

    IMPORTANT: When you configure classes, use configure_classes_for_testing()
    to get automatic cleanup. Or manually call track_configured_class().

    Example (recommended - automatic cleanup):
        from tests.mocks import configure_classes_for_testing

        def test_user_service(mock_app_manager):
            mock_app_manager.register_entity("users", User)

            configure_classes_for_testing(mock_app_manager, UserService)

            # Test your service
            assert UserService.entity_class == User
            # Cleanup happens automatically!

    Example (manual tracking):
        def test_user_service(mock_app_manager):
            from tests.mocks.utils import track_configured_class

            mock_app_manager.register_entity("users", User)
            UserService.configure_app_manager_for_testing(mock_app_manager)
            track_configured_class(UserService)  # Manual tracking

            # Test...
    """
    return MockAppManager()


@pytest.fixture
def mock_db_session():
    """
    Mock database session for unit tests.

    Returns an AsyncMock that mimics AsyncSession interface.
    You can configure specific behaviors as needed.

    Example:
        async def test_get_user(mock_db_session):
            # Configure mock behavior
            mock_db_session.execute.return_value.scalar_one_or_none.return_value = user

            result = await UserService.get_by_id("123", mock_db_session)
            assert result == user
    """
    session = AsyncMock()
    # Configure common session methods
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = Mock()
    return session
