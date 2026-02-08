"""
Pytest configuration for file_management integration tests.

Provides a session-scoped AppManager with file_management app loaded,
including StoredFileType and FileImportStatus/Type parametric data.
"""

import pytest_asyncio

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager


@pytest_asyncio.fixture(scope="session")
async def file_management_app_manager():
    """Create AppManager with file_management app loaded."""
    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=":memory:",
        echo=False
    )
    settings.apps = [
        "lys.apps.base",
        "lys.apps.file_management",
    ]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await app_manager.database.initialize_database()

    # Seed parametric data
    async with app_manager.database.get_session() as session:
        # Languages (needed by base)
        language_service = app_manager.get_service("language")
        await language_service.create(session=session, id="en", enabled=True)

        # StoredFileType
        stored_file_type_service = app_manager.get_service("stored_file_type")
        await stored_file_type_service.create(session=session, id="USER_IMPORT_FILE", enabled=True)
        await stored_file_type_service.create(session=session, id="DOCUMENT", enabled=True)

        # FileImportType
        file_import_type_service = app_manager.get_service("file_import_type")
        await file_import_type_service.create(session=session, id="USER_IMPORT", enabled=True)

        # FileImportStatus
        from lys.apps.file_management.modules.file_import.consts import (
            FILE_IMPORT_STATUS_PENDING, FILE_IMPORT_STATUS_PROCESSING,
            FILE_IMPORT_STATUS_COMPLETED, FILE_IMPORT_STATUS_FAILED
        )
        file_import_status_service = app_manager.get_service("file_import_status")
        await file_import_status_service.create(
            session=session, id=FILE_IMPORT_STATUS_PENDING, enabled=True
        )
        await file_import_status_service.create(
            session=session, id=FILE_IMPORT_STATUS_PROCESSING, enabled=True
        )
        await file_import_status_service.create(
            session=session, id=FILE_IMPORT_STATUS_COMPLETED, enabled=True
        )
        await file_import_status_service.create(
            session=session, id=FILE_IMPORT_STATUS_FAILED, enabled=True
        )

        await session.commit()

    yield app_manager
    await app_manager.database.close()
