"""
Database fixtures for integration tests.

Provides fixtures for testing with real SQLite in-memory database.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager


@pytest_asyncio.fixture
async def test_app_manager():
    """
    Create a real AppManager configured for testing with SQLite in-memory.

    This fixture provides a fully functional AppManager with:
    - SQLite in-memory database (fast, isolated)
    - All components loaded (entities, services, fixtures)
    - Database initialized and ready

    Use this for integration tests that need real database operations.

    Example:
        @pytest.mark.asyncio
        async def test_user_crud(test_app_manager):
            async with test_app_manager.database.get_session() as session:
                user = await UserService.create(session, email="test@test.com")
                assert user.id is not None
    """
    # Configure test settings with SQLite
    test_settings = LysAppSettings()
    test_settings.database.configure(
        type="sqlite",
        database=":memory:",  # In-memory database (destroyed after test)
        echo=False  # Set to True for SQL debugging
    )

    # Create AppManager with test settings
    app_manager = AppManager(settings=test_settings)

    # Configure which component types to load
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
        # Note: We don't load FIXTURES in tests to avoid side effects
        # Tests should create their own data
    ])

    # Load all components
    app_manager.load_all_components()

    # Initialize database (create tables)
    if app_manager.database.has_database_configured():
        await app_manager.database.initialize_database()

    yield app_manager

    # Cleanup - close database connection
    await app_manager.database.close()


@pytest_asyncio.fixture
async def db_session(test_app_manager):
    """
    Get a database session for integration tests.

    This fixture provides a database session that:
    - Is connected to the test SQLite database
    - Automatically rolls back after the test (isolation)
    - Cleans up connections properly

    Example:
        @pytest.mark.asyncio
        async def test_create_user(db_session):
            user = await UserService.create(
                db_session,
                email="test@test.com"
            )
            assert user.id is not None
            # Rollback happens automatically!
    """
    async with test_app_manager.database.get_session() as session:
        yield session
        # Rollback to ensure test isolation
        await session.rollback()


@pytest_asyncio.fixture
async def db_session_commit(test_app_manager):
    """
    Get a database session that COMMITS changes.

    Use this when you need changes to persist across multiple operations
    in the same test.

    WARNING: Changes are NOT rolled back. Use with caution or in isolated tests.

    Example:
        @pytest.mark.asyncio
        async def test_user_workflow(db_session_commit):
            # Create user
            user = await UserService.create(
                db_session_commit,
                email="test@test.com"
            )
            await db_session_commit.commit()

            # User exists in a new query
            found = await UserService.get_by_id(user.id, db_session_commit)
            assert found is not None
    """
    async with test_app_manager.database.get_session() as session:
        yield session
        # No automatic rollback - test decides when to commit
