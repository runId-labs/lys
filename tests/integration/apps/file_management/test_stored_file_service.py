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

from lys.apps.file_management.modules.stored_file.consts import ZIP_MAGIC_BYTES
from lys.core.utils.storage import StorageError


def _s3_error(code: str) -> StorageError:
    """StorageError wrapping a botocore-shaped error, as the S3 backend raises it."""
    original = Exception("boom")
    original.response = {"Error": {"Code": code}}
    return StorageError("boom", "head_object", original)


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


class TestStoredFileServiceContentHash:
    """Test that upload persists the SHA-256 content_hash for in-memory bytes."""

    @pytest.mark.asyncio
    async def test_upload_persists_content_hash(self, file_management_app_manager):
        """Uploading bytes stores their SHA-256 hex digest on the record."""
        import hashlib

        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        data = b"hashable content"

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                stored_file = await stored_file_service.upload(
                    session=session,
                    client_id=str(uuid4()),
                    data=data,
                    original_name="hashed.csv",
                    size=len(data),
                    mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                assert stored_file.content_hash == hashlib.sha256(data).hexdigest()

    @pytest.mark.asyncio
    async def test_upload_same_content_same_hash(self, file_management_app_manager):
        """Two uploads of identical content produce the same content_hash."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        data = b"identical payload"

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                first = await stored_file_service.upload(
                    session=session, client_id=str(uuid4()), data=data,
                    original_name="a.csv", size=len(data), mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )
                second = await stored_file_service.upload(
                    session=session, client_id=str(uuid4()), data=data,
                    original_name="b.csv", size=len(data), mime_type="text/csv",
                    type_id="USER_IMPORT_FILE"
                )

                assert first.content_hash == second.content_hash


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


class TestStoredFileServiceSoftDelete:
    """Test StoredFileService.soft_delete_file: S3 bytes purged, row kept as a tombstone."""

    async def _upload(self, service, session, data=b"purge me"):
        return await service.upload(
            session=session,
            client_id=str(uuid4()),
            data=data,
            original_name="purge.csv",
            size=len(data),
            mime_type="text/csv",
            type_id="USER_IMPORT_FILE",
        )

    @pytest.mark.asyncio
    async def test_purges_bytes_and_keeps_the_row(self, file_management_app_manager):
        """The S3 object is deleted, the row survives with deleted_at set."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                stored_file = await self._upload(stored_file_service, session)
                file_id = stored_file.id
                original_hash = stored_file.content_hash

                await stored_file_service.soft_delete_file(session, stored_file)
                await session.commit()

                mock_storage.delete.assert_called_once()

                # The row is still readable, flagged, and keeps its dedup hash.
                tombstone = await session.get(stored_file_service.entity_class, file_id)
                assert tombstone is not None
                assert tombstone.deleted_at is not None
                assert tombstone.content_hash == original_hash

    @pytest.mark.asyncio
    async def test_is_a_no_op_on_an_existing_tombstone(self, file_management_app_manager):
        """Soft deleting twice does not re-purge nor refresh the timestamp."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                stored_file = await self._upload(stored_file_service, session, data=b"purge twice")

                await stored_file_service.soft_delete_file(session, stored_file)
                await session.commit()
                first_timestamp = stored_file.deleted_at

                await stored_file_service.soft_delete_file(session, stored_file)
                await session.commit()

                mock_storage.delete.assert_called_once()
                assert stored_file.deleted_at == first_timestamp

    @pytest.mark.asyncio
    async def test_tombstone_still_matches_the_idempotency_lookup(self, file_management_app_manager):
        """A purged file keeps feeding content-hash dedup: same hash still queryable."""
        from sqlalchemy import select

        stored_file_service = file_management_app_manager.get_service("stored_file")
        entity = stored_file_service.entity_class
        mock_storage = AsyncMock()
        data = b"deduplicated payload"

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                stored_file = await self._upload(stored_file_service, session, data=data)
                client_id = stored_file.client_id
                content_hash = stored_file.content_hash

                await stored_file_service.soft_delete_file(session, stored_file)
                await session.commit()

                # The (client_id, content_hash) lookup used by find_active_import
                # deliberately does not filter tombstones.
                result = await session.execute(
                    select(entity).where(
                        entity.client_id == client_id,
                        entity.content_hash == content_hash,
                    )
                )
                match = result.scalars().first()
                assert match is not None
                assert match.deleted_at is not None


class TestStoredFileServiceCreateFromUploaded:
    """Test StoredFileService.create_from_uploaded with mocked storage."""

    @pytest.mark.asyncio
    async def test_create_from_uploaded_success(self, file_management_app_manager):
        """Test creating record for a file uploaded via presigned URL."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        mock_storage.head_object.return_value = {"size": 1024, "content_type": "application/pdf"}

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
                mock_storage.head_object.assert_called_once_with(object_key)
                mock_storage.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_from_uploaded_file_not_found(self, file_management_app_manager):
        """Test that create_from_uploaded raises when file doesn't exist."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        mock_storage = AsyncMock()
        mock_storage.head_object.side_effect = _s3_error("404")

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="File not found"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=client_id,
                        object_key=f"{client_id}/DOCUMENT/missing.pdf",
                        original_name="missing.pdf",
                        size=0,
                        mime_type="application/pdf",
                        type_id="DOCUMENT"
                    )

                # A missing object was never created: nothing to purge.
                mock_storage.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_backend_failure_is_not_reported_as_not_found(self, file_management_app_manager):
        """A storage outage propagates instead of masquerading as a missing file."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        mock_storage = AsyncMock()
        mock_storage.head_object.side_effect = _s3_error("500")

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(StorageError):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=client_id,
                        object_key=f"{client_id}/DOCUMENT/unreachable.pdf",
                        original_name="unreachable.pdf",
                        size=10,
                        mime_type="application/pdf",
                        type_id="DOCUMENT"
                    )

    @pytest.mark.asyncio
    async def test_rejects_an_object_key_owned_by_another_client(self, file_management_app_manager):
        """The key is client input: another tenant's key is refused before any purge."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        mock_storage = AsyncMock()
        victim_key = f"{uuid4()}/DOCUMENT/2024/01/01/{uuid4()}.pdf"

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="does not belong to this client"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=str(uuid4()),  # attacker's own client
                        object_key=victim_key,
                        original_name="steal.pdf",
                        size=1,  # wrong size: would trigger the purge branch
                        mime_type="application/pdf",
                        type_id="DOCUMENT"
                    )

                # The victim's object must not be touched, read or deleted.
                mock_storage.head_object.assert_not_called()
                mock_storage.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_size_mismatch_rejects_and_purges(self, file_management_app_manager):
        """The declared size is a claim: a mismatch rejects the upload and purges it."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        object_key = f"{client_id}/DOCUMENT/2024/01/01/{uuid4()}.pdf"
        mock_storage = AsyncMock()
        mock_storage.head_object.return_value = {"size": 9_999, "content_type": "application/pdf"}

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="File size mismatch"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=client_id,
                        object_key=object_key,
                        original_name="lying.pdf",
                        size=10,
                        mime_type="application/pdf",
                        type_id="DOCUMENT"
                    )

                mock_storage.delete.assert_called_once_with(object_key)

    @pytest.mark.asyncio
    async def test_max_size_rejects_and_purges(self, file_management_app_manager):
        """An oversized upload is rejected on its actual size, not the declared one."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        object_key = f"{client_id}/DOCUMENT/2024/01/01/{uuid4()}.pdf"
        mock_storage = AsyncMock()
        mock_storage.head_object.return_value = {"size": 5_000, "content_type": "application/pdf"}

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="exceeds maximum size"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=client_id,
                        object_key=object_key,
                        original_name="huge.pdf",
                        size=5_000,
                        mime_type="application/pdf",
                        type_id="DOCUMENT",
                        max_size=1_000,
                    )

                mock_storage.delete.assert_called_once_with(object_key)

    @pytest.mark.asyncio
    async def test_validate_zip_rejects_a_non_archive(self, file_management_app_manager):
        """With validate_zip on, the stored bytes must start with the ZIP magic."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        object_key = f"{client_id}/DOCUMENT/2024/01/01/{uuid4()}.zip"
        mock_storage = AsyncMock()
        mock_storage.head_object.return_value = {"size": 4, "content_type": "application/zip"}
        mock_storage.download_range.return_value = b"%PDF"

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="not a valid ZIP archive"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=client_id,
                        object_key=object_key,
                        original_name="fake.zip",
                        size=4,
                        mime_type="application/zip",
                        type_id="DOCUMENT",
                        validate_zip=True,
                    )

                mock_storage.download_range.assert_called_once_with(object_key, 0, 3)
                mock_storage.delete.assert_called_once_with(object_key)

    @pytest.mark.asyncio
    async def test_validate_zip_accepts_an_archive(self, file_management_app_manager):
        """A real ZIP header passes the check."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        object_key = f"{client_id}/DOCUMENT/2024/01/01/{uuid4()}.zip"
        mock_storage = AsyncMock()
        mock_storage.head_object.return_value = {"size": 4, "content_type": "application/zip"}
        mock_storage.download_range.return_value = ZIP_MAGIC_BYTES

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                stored_file = await stored_file_service.create_from_uploaded(
                    session=session,
                    client_id=client_id,
                    object_key=object_key,
                    original_name="real.zip",
                    size=4,
                    mime_type="application/zip",
                    type_id="DOCUMENT",
                    validate_zip=True,
                    content_hash="a" * 64,
                )

                assert stored_file.content_hash == "a" * 64
                mock_storage.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_purge_failure_does_not_mask_the_validation_error(self, file_management_app_manager):
        """A failing purge is logged; the caller still sees why the upload was rejected."""
        stored_file_service = file_management_app_manager.get_service("stored_file")
        client_id = str(uuid4())
        object_key = f"{client_id}/DOCUMENT/2024/01/01/{uuid4()}.pdf"
        mock_storage = AsyncMock()
        mock_storage.head_object.return_value = {"size": 9_999, "content_type": "application/pdf"}
        mock_storage.delete.side_effect = RuntimeError("S3 unreachable")

        with patch.object(stored_file_service, "get_storage_backend", return_value=mock_storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="File size mismatch"):
                    await stored_file_service.create_from_uploaded(
                        session=session,
                        client_id=client_id,
                        object_key=object_key,
                        original_name="lying.pdf",
                        size=10,
                        mime_type="application/pdf",
                        type_id="DOCUMENT"
                    )
