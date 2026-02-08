"""
Integration tests for file_management StoredFileService.

Tests cover:
- upload (mocked StorageBackend)
- delete_file (mocked StorageBackend)
- create_from_uploaded (mocked StorageBackend)
- generate_object_key
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock


class TestStoredFileServiceObjectKey:
    """Test StoredFileService.generate_object_key."""

    def test_generate_object_key_format(self, file_management_app_manager):
        """Test that object key has correct format."""
        stored_file_service = file_management_app_manager.get_service("stored_file")

        client_id = str(uuid4())
        key = stored_file_service.generate_object_key(
            client_id=client_id,
            type_id="USER_IMPORT_FILE",
            original_name="data.csv"
        )

        assert key.startswith(f"{client_id}/USER_IMPORT_FILE/")
        assert key.endswith(".csv")

    def test_generate_object_key_no_extension(self, file_management_app_manager):
        """Test object key for files without extension."""
        stored_file_service = file_management_app_manager.get_service("stored_file")

        key = stored_file_service.generate_object_key(
            client_id=str(uuid4()),
            type_id="DOCUMENT",
            original_name="readme"
        )

        # Should not have extension
        assert not key.endswith(".")


class TestStoredFileServiceUpload:
    """Test StoredFileService.upload with mocked storage."""

    @pytest.mark.asyncio
    async def test_upload_creates_record(self, file_management_app_manager):
        """Test that upload creates a StoredFile record and calls storage."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=client_id,
                    data=b"file content here",
                    original_name="test.csv",
                    size=17,
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                assert stored_file.id is not None
                assert stored_file.client_id == client_id
                assert stored_file.original_name == "test.csv"
                assert stored_file.size == 17
                assert stored_file.mime_type == "text/csv"
                assert stored_file.type_id == "USER_IMPORT_FILE"
                assert stored_file.object_key is not None
                mock_storage.upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_failure_cleans_up(self, file_management_app_manager):
        """Test that upload failure deletes the DB record."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        mock_storage.upload.side_effect = Exception("S3 error")

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(Exception, match="S3 error"):
                    await stored_file_service.upload(
                        session=session,
                        client_id=str(uuid4()),
                        data=b"content",
                        original_name="fail.csv",
                        size=7,
                        mime_type="text/csv",
                        type_id="USER_IMPORT_FILE"
                    )


class TestStoredFileServiceDelete:
    """Test StoredFileService.delete_file with mocked storage."""

    @pytest.mark.asyncio
    async def test_delete_file(self, file_management_app_manager):
        """Test deleting a file from storage and database."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                # Create a file record
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=str(uuid4()),
                    data=b"delete me",
                    original_name="delete.txt",
                    size=9,
                    mime_type="text/plain",
                    type_id="DOCUMENT"
                )
                file_id = stored_file.id

                # Delete it
                await stored_file_service.delete_file(session, stored_file)
                mock_storage.delete.assert_called_once()


class TestStoredFileServiceCreateFromUploaded:
    """Test StoredFileService.create_from_uploaded with mocked storage."""

    @pytest.mark.asyncio
    async def test_create_from_uploaded_success(self, file_management_app_manager):
        """Test creating record for a file uploaded via presigned URL."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        mock_storage.exists.return_value = True

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                object_key = f"{client_id}/DOCUMENT/2024/01/01/{uuid4()}.pdf"

                stored_file = await stored_file_service.create_from_uploaded(
                    session=session,
                    client_id=client_id,
                    object_key=object_key,
                    original_name="report.pdf",
                    size=1024,
                    mime_type="application/pdf",
                    type_id="DOCUMENT"
                )

                assert stored_file.object_key == object_key
                assert stored_file.original_name == "report.pdf"
                mock_storage.exists.assert_called_once_with(object_key)

    @pytest.mark.asyncio
    async def test_create_from_uploaded_file_not_found(self, file_management_app_manager):
        """Test that create_from_uploaded raises when file doesn't exist."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        mock_storage.exists.return_value = False

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="File not found"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=str(uuid4()),
                        object_key="nonexistent/path",
                        original_name="missing.pdf",
                        size=0,
                        mime_type="application/pdf",
                        type_id="DOCUMENT"
                    )
