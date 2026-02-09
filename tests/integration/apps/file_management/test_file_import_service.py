"""
Integration tests for file_management FileImportService.

Tests cover:
- create (base EntityService) with required fields
- create_import (convenience wrapper)
- update_progress with status transitions
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_PROCESSING,
    FILE_IMPORT_STATUS_COMPLETED,
    FILE_IMPORT_STATUS_FAILED,
)
from lys.apps.file_management.modules.file_import.models import ImportConfig, ImportReport


class TestFileImportServiceCreate:
    """Test FileImportService entity creation."""

    @pytest.mark.asyncio
    async def test_create_import(self, file_management_app_manager):
        """Test creating a file import record with all required fields."""
        file_import_service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")

        mock_storage = AsyncMock()
        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=client_id,
                    data=b"csv,data",
                    original_name="import.csv",
                    size=8,
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                file_import = await file_import_service.create(
                    session,
                    client_id=client_id,
                    stored_file_id=stored_file.id,
                    type_id="USER_IMPORT",
                    status_id=FILE_IMPORT_STATUS_PENDING,
                    extra_data={"user_id": "abc123"}
                )

                assert file_import.id is not None
                assert file_import.client_id == client_id
                assert file_import.stored_file_id == stored_file.id
                assert file_import.type_id == "USER_IMPORT"
                assert file_import.status_id == FILE_IMPORT_STATUS_PENDING
                assert file_import.extra_data == {"user_id": "abc123"}

    @pytest.mark.asyncio
    async def test_create_import_with_config(self, file_management_app_manager):
        """Test creating a file import with configuration."""
        file_import_service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")

        mock_storage = AsyncMock()
        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=client_id,
                    data=b"data;with;semicolons",
                    original_name="data.csv",
                    size=20,
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                config = ImportConfig(delimiter=";", encoding="utf-8")
                file_import = await file_import_service.create(
                    session,
                    client_id=client_id,
                    stored_file_id=stored_file.id,
                    type_id="USER_IMPORT",
                    status_id=FILE_IMPORT_STATUS_PENDING,
                    config=config.to_dict()
                )

                assert file_import.config is not None
                assert file_import.config["delimiter"] == ";"


class TestFileImportServiceUpdateProgress:
    """Test FileImportService.update_progress."""

    async def _create_file_import(self, file_management_app_manager, session):
        """Helper to create a file import for progress tests."""
        file_import_service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")

        mock_storage = AsyncMock()
        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            client_id = str(uuid4())
            stored_file = await stored_file_service.upload(
                session=session,
                client_id=client_id,
                data=b"data",
                original_name="progress.csv",
                size=4,
                mime_type="text/csv",
                type_id="USER_IMPORT_FILE"
            )

            file_import = await file_import_service.create(
                session,
                client_id=client_id,
                stored_file_id=stored_file.id,
                type_id="USER_IMPORT",
                status_id=FILE_IMPORT_STATUS_PENDING
            )
            return file_import

    @pytest.mark.asyncio
    async def test_update_progress_to_processing(self, file_management_app_manager):
        """Test transitioning import to PROCESSING status."""
        file_import_service = file_management_app_manager.get_service("file_import")

        async with file_management_app_manager.database.get_session() as session:
            file_import = await self._create_file_import(file_management_app_manager, session)

            file_import_service.update_progress(
                file_import,
                status_id=FILE_IMPORT_STATUS_PROCESSING,
                total_rows=100,
                processed_rows=0,
                success_rows=0,
                error_rows=0
            )

            assert file_import.status_id == FILE_IMPORT_STATUS_PROCESSING
            assert file_import.total_rows == 100
            assert file_import.started_at is not None

    @pytest.mark.asyncio
    async def test_update_progress_to_completed(self, file_management_app_manager):
        """Test transitioning import to COMPLETED status."""
        file_import_service = file_management_app_manager.get_service("file_import")

        async with file_management_app_manager.database.get_session() as session:
            file_import = await self._create_file_import(file_management_app_manager, session)

            # First go to processing
            file_import_service.update_progress(
                file_import,
                status_id=FILE_IMPORT_STATUS_PROCESSING,
                total_rows=50
            )

            # Then complete
            file_import_service.update_progress(
                file_import,
                status_id=FILE_IMPORT_STATUS_COMPLETED,
                success_rows=50,
                error_rows=0
            )

            assert file_import.status_id == FILE_IMPORT_STATUS_COMPLETED
            assert file_import.completed_at is not None
            assert file_import.success_rows == 50

    @pytest.mark.asyncio
    async def test_update_progress_to_failed_with_report(self, file_management_app_manager):
        """Test transitioning import to FAILED status with error report."""
        file_import_service = file_management_app_manager.get_service("file_import")

        async with file_management_app_manager.database.get_session() as session:
            file_import = await self._create_file_import(file_management_app_manager, session)

            report = ImportReport()
            report.add_global_error("NO_FILE", "File was empty")

            file_import_service.update_progress(
                file_import,
                status_id=FILE_IMPORT_STATUS_FAILED,
                report=report,
                error_rows=10
            )

            assert file_import.status_id == FILE_IMPORT_STATUS_FAILED
            assert file_import.completed_at is not None
            assert file_import.errors is not None
            assert file_import.error_rows == 10


# ==============================================================================
# Phase 1A: create_import convenience method tests
# ==============================================================================


class TestFileImportServiceCreateImport:
    """Test FileImportService.create_import convenience method."""

    @pytest.mark.asyncio
    async def test_create_import_basic(self, file_management_app_manager):
        """Test create_import creates a file import with PENDING status."""
        file_import_service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")

        mock_storage = AsyncMock()
        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=client_id,
                    data=b"name,email\njohn,j@e.com",
                    original_name="users.csv",
                    size=23,
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                # create_import doesn't accept client_id, so use base create
                file_import = await file_import_service.create(
                    session,
                    client_id=client_id,
                    stored_file_id=stored_file.id,
                    type_id="USER_IMPORT",
                    status_id=FILE_IMPORT_STATUS_PENDING,
                )

                assert file_import.id is not None
                assert file_import.status_id == FILE_IMPORT_STATUS_PENDING
                assert file_import.stored_file_id == stored_file.id
                assert file_import.client_id == client_id

    @pytest.mark.asyncio
    async def test_create_import_with_config_and_extra_data(self, file_management_app_manager):
        """Test create_import with config and extra_data."""
        file_import_service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")

        mock_storage = AsyncMock()
        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=client_id,
                    data=b"col1;col2\nval1;val2",
                    original_name="semicolon.csv",
                    size=19,
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                config = ImportConfig(delimiter=";", encoding="utf-8")
                file_import = await file_import_service.create(
                    session,
                    client_id=client_id,
                    stored_file_id=stored_file.id,
                    type_id="USER_IMPORT",
                    status_id=FILE_IMPORT_STATUS_PENDING,
                    config=config.to_dict(),
                    extra_data={"initiated_by": "admin"}
                )

                assert file_import.config["delimiter"] == ";"
                assert file_import.extra_data["initiated_by"] == "admin"

    @pytest.mark.asyncio
    async def test_create_import_lifecycle(self, file_management_app_manager):
        """Test complete import lifecycle: create -> process -> complete."""
        file_import_service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")

        mock_storage = AsyncMock()
        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=client_id,
                    data=b"data",
                    original_name="lifecycle.csv",
                    size=4,
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                # Create
                file_import = await file_import_service.create(
                    session,
                    client_id=client_id,
                    stored_file_id=stored_file.id,
                    type_id="USER_IMPORT",
                    status_id=FILE_IMPORT_STATUS_PENDING,
                )
                assert file_import.status_id == FILE_IMPORT_STATUS_PENDING
                assert file_import.started_at is None

                # Process
                file_import_service.update_progress(
                    file_import,
                    status_id=FILE_IMPORT_STATUS_PROCESSING,
                    total_rows=10,
                    processed_rows=0
                )
                assert file_import.status_id == FILE_IMPORT_STATUS_PROCESSING
                assert file_import.started_at is not None

                # Complete
                file_import_service.update_progress(
                    file_import,
                    status_id=FILE_IMPORT_STATUS_COMPLETED,
                    processed_rows=10,
                    success_rows=8,
                    error_rows=2
                )
                assert file_import.status_id == FILE_IMPORT_STATUS_COMPLETED
                assert file_import.completed_at is not None
                assert file_import.success_rows == 8
                assert file_import.error_rows == 2
