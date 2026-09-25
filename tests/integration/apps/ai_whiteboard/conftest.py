"""
Pytest configuration for whiteboard integration tests.

AppManager with ``lys.apps.ai_whiteboard`` loaded on an in-memory database. No LLM call,
no pubsub: the signals are covered by unit tests, and the writes are what matter here.
"""

import pytest_asyncio

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager
from tests.fixtures.database import create_all_tables


@pytest_asyncio.fixture(scope="session")
async def whiteboard_app_manager():
    """Create AppManager with the AI and whiteboard apps loaded."""
    settings = LysAppSettings()
    settings.database.configure(type="sqlite", database=":memory:", echo=False)
    settings.apps = [
        "lys.apps.base",
        "lys.apps.user_auth",
        "lys.apps.ai",
        "lys.apps.ai_whiteboard",
    ]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await create_all_tables(app_manager.database)

    yield app_manager
    await app_manager.database.close()
