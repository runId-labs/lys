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
import pytest_asyncio
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

    Note: Some integration tests may still have isolation issues when run together.
    Run integration test files individually for best results:
        pytest tests/integration/test_language_service.py -v
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


# ==============================================================================
# Shared fixtures for user_auth integration tests
# ==============================================================================


@pytest_asyncio.fixture(scope="session")
async def user_auth_app_manager():
    """Create AppManager with user_auth app loaded (shared across entire test session)."""
    from lys.core.configs import LysAppSettings
    from lys.core.consts.component_types import AppComponentTypeEnum
    from lys.core.managers.app import AppManager

    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=":memory:",
        echo=False
    )
    settings.apps = ["lys.apps.base", "lys.apps.user_auth"]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await app_manager.database.initialize_database()

    # Create base test data (languages, genders, emailing types, etc.)
    language_service = app_manager.get_service("language")
    gender_service = app_manager.get_service("gender")
    emailing_type_service = app_manager.get_service("emailing_type")
    emailing_status_service = app_manager.get_service("emailing_status")
    one_time_token_type_service = app_manager.get_service("one_time_token_type")

    async with app_manager.database.get_session() as session:
        # Create test languages
        await language_service.create(session=session, id="en", enabled=True)
        await language_service.create(session=session, id="fr", enabled=True)

        # Create test genders
        await gender_service.create(session=session, id="M", enabled=True)
        await gender_service.create(session=session, id="F", enabled=True)

        # Create emailing types
        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        await emailing_type_service.create(
            session=session,
            id=USER_PASSWORD_RESET_EMAILING_TYPE,
            enabled=True,
            subject="Password Reset",
            template="password_reset",
            context_description={}
        )

        # Create emailing statuses
        await emailing_status_service.create(session=session, id="PENDING", enabled=True)
        await emailing_status_service.create(session=session, id="SENT", enabled=True)

        # Create one-time token types (duration in minutes)
        from lys.apps.base.modules.one_time_token.consts import (
            PASSWORD_RESET_TOKEN_TYPE,
            EMAIL_VERIFICATION_TOKEN_TYPE
        )
        await one_time_token_type_service.create(
            session=session,
            id=PASSWORD_RESET_TOKEN_TYPE,
            enabled=True,
            duration=30  # 30 minutes
        )
        await one_time_token_type_service.create(
            session=session,
            id=EMAIL_VERIFICATION_TOKEN_TYPE,
            enabled=True,
            duration=1440  # 24 hours
        )

        # Create one-time token statuses
        from lys.apps.base.modules.one_time_token.consts import (
            PENDING_TOKEN_STATUS,
            USED_TOKEN_STATUS,
            REVOKED_TOKEN_STATUS
        )
        one_time_token_status_service = app_manager.get_service("one_time_token_status")
        await one_time_token_status_service.create(session=session, id=PENDING_TOKEN_STATUS, enabled=True)
        await one_time_token_status_service.create(session=session, id=USED_TOKEN_STATUS, enabled=True)
        await one_time_token_status_service.create(session=session, id=REVOKED_TOKEN_STATUS, enabled=True)

        # Create user statuses
        from lys.apps.user_auth.modules.user.consts import (
            ENABLED_USER_STATUS,
            DISABLED_USER_STATUS,
            REVOKED_USER_STATUS,
            DELETED_USER_STATUS
        )
        user_status_service = app_manager.get_service("user_status")
        await user_status_service.create(session=session, id=ENABLED_USER_STATUS, enabled=True)
        await user_status_service.create(session=session, id=DISABLED_USER_STATUS, enabled=True)
        await user_status_service.create(session=session, id=REVOKED_USER_STATUS, enabled=True)
        await user_status_service.create(session=session, id=DELETED_USER_STATUS, enabled=True)

        # Create user audit log types
        from lys.apps.user_auth.modules.user.consts import (
            STATUS_CHANGE_LOG_TYPE,
            ANONYMIZATION_LOG_TYPE,
            OBSERVATION_LOG_TYPE
        )
        user_audit_log_type_service = app_manager.get_service("user_audit_log_type")
        await user_audit_log_type_service.create(session=session, id=STATUS_CHANGE_LOG_TYPE, enabled=True)
        await user_audit_log_type_service.create(session=session, id=ANONYMIZATION_LOG_TYPE, enabled=True)
        await user_audit_log_type_service.create(session=session, id=OBSERVATION_LOG_TYPE, enabled=True)

        # Create login attempt statuses (for AuthService tests)
        from lys.apps.user_auth.modules.auth.consts import (
            FAILED_LOGIN_ATTEMPT_STATUS,
            SUCCEED_LOGIN_ATTEMPT_STATUS
        )
        login_attempt_status_service = app_manager.get_service("login_attempt_status")
        await login_attempt_status_service.create(session=session, id=FAILED_LOGIN_ATTEMPT_STATUS, enabled=True)
        await login_attempt_status_service.create(session=session, id=SUCCEED_LOGIN_ATTEMPT_STATUS, enabled=True)

        await session.commit()

    yield app_manager

    await app_manager.database.close()
