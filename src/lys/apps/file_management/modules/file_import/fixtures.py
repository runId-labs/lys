"""
Fixtures for file import status configuration.

This module provides the initial data for file import statuses.
These fixtures are loaded automatically during application startup.
"""
from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_PROCESSING,
    FILE_IMPORT_STATUS_COMPLETED,
    FILE_IMPORT_STATUS_FAILED,
    FILE_IMPORT_STATUS_CANCELLED,
)
from lys.apps.file_management.modules.file_import.services import FileImportStatusService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class FileImportStatusFixtures(EntityFixtures[FileImportStatusService]):
    """
    Fixtures for FileImportStatus entities.

    Statuses:
        - PENDING: Import job is waiting to be processed
        - PROCESSING: Import job is currently being processed
        - COMPLETED: Import job finished successfully
        - FAILED: Import job failed with errors
        - CANCELLED: Import job was cancelled
    """

    model = ParametricEntityFixturesModel

    data_list = [
        {
            "id": FILE_IMPORT_STATUS_PENDING,
            "attributes": {
                "enabled": True,
                "description": "Import job is waiting to be processed."
            }
        },
        {
            "id": FILE_IMPORT_STATUS_PROCESSING,
            "attributes": {
                "enabled": True,
                "description": "Import job is currently being processed."
            }
        },
        {
            "id": FILE_IMPORT_STATUS_COMPLETED,
            "attributes": {
                "enabled": True,
                "description": "Import job finished successfully."
            }
        },
        {
            "id": FILE_IMPORT_STATUS_FAILED,
            "attributes": {
                "enabled": True,
                "description": "Import job failed with errors."
            }
        },
        {
            "id": FILE_IMPORT_STATUS_CANCELLED,
            "attributes": {
                "enabled": True,
                "description": "Import job was cancelled."
            }
        },
    ]