"""
Integration tests for FileImportService.stage_document() and find_active_import_async().

stage_document stages a single already-uploaded document (presigned upload flow):
StoredFile + PENDING FileImport, or a SKIPPED FileImport on a content-hash duplicate.
The storage backend is mocked; the database is real.
"""

import hashlib
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_COMPLETED,
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_SKIPPED,
)


CONTENT = b"col_a,col_b\n1,2\n"


def _mock_storage(size=len(CONTENT)):
    storage = AsyncMock()
    storage.head_object.return_value = {"size": size, "content_type": "text/csv"}
    return storage


async def _stage(service, session, *, client_id, object_key=None, content=CONTENT, **kwargs):
    return await service.stage_document(
        session,
        client_id=client_id,
        object_key=object_key or f"{client_id}/USER_IMPORT_FILE/2026/01/01/{uuid4()}.csv",
        original_name="data.csv",
        size=len(content),
        content=content,
        mime_type="text/csv",
        stored_file_type_id="USER_IMPORT_FILE",
        import_type_id="USER_IMPORT",
        **kwargs,
    )


class TestStageDocument:
    """Nominal staging: one StoredFile + one PENDING FileImport."""

    @pytest.mark.asyncio
    async def test_creates_stored_file_and_pending_import(self, file_management_app_manager):
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                staged = await _stage(service, session, client_id=client_id)

                assert staged.is_duplicate is False
                assert staged.stored_file_id is not None

                file_import = await session.get(service.entity_class, staged.file_import_id)
                assert file_import.status_id == FILE_IMPORT_STATUS_PENDING
                assert file_import.extra_data["original_file_name"] == "data.csv"

                stored_file = await session.get(
                    stored_file_service.entity_class, staged.stored_file_id
                )
                # The hash comes from the content the caller read, not from a download.
                assert stored_file.content_hash == hashlib.sha256(CONTENT).hexdigest()
                storage.download.assert_not_called()

    @pytest.mark.asyncio
    async def test_forwards_fields_to_one_record_only(self, file_management_app_manager):
        """file_import_fields targets the FileImport, not the StoredFile.

        ``config`` exists on FileImport only: passing it through the shared
        ``entity_fields`` would blow up on the StoredFile record.
        """
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                staged = await _stage(
                    service, session, client_id=str(uuid4()),
                    file_import_fields={"config": {"delimiter": ";"}},
                )

                file_import = await session.get(service.entity_class, staged.file_import_id)
                assert file_import.config == {"delimiter": ";"}

    @pytest.mark.asyncio
    async def test_rejects_extra_fields_overriding_staging_columns(self, file_management_app_manager):
        """A reserved column in the extra dicts is a clear error, not a raw TypeError."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="cannot override staging columns"):
                    await _stage(
                        service, session, client_id=str(uuid4()),
                        stored_file_fields={"content_hash": "forged"},
                    )

                storage.head_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_a_key_owned_by_another_client(self, file_management_app_manager):
        """The object key is client input: another tenant's key is refused untouched."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="does not belong to this client"):
                    await _stage(
                        service, session,
                        client_id=str(uuid4()),
                        object_key=f"{uuid4()}/USER_IMPORT_FILE/2026/01/01/victim.csv",
                    )

                storage.head_object.assert_not_called()
                storage.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_size_mismatch_is_rejected(self, file_management_app_manager):
        """The declared size is checked against the stored object."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage(size=999_999)

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="File size mismatch"):
                    await _stage(service, session, client_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_max_size_is_forwarded(self, file_management_app_manager):
        """max_size reaches create_from_uploaded instead of being unreachable."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="exceeds maximum size"):
                    await _stage(service, session, client_id=str(uuid4()), max_size=1)

    @pytest.mark.asyncio
    async def test_validate_zip_is_forwarded(self, file_management_app_manager):
        """validate_zip reaches create_from_uploaded and rejects a non-archive."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()
        storage.download_range.return_value = b"col_"

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                with pytest.raises(ValueError, match="not a valid ZIP archive"):
                    await _stage(service, session, client_id=str(uuid4()), validate_zip=True)


class TestStageDocumentIdempotency:
    """Content-hash idempotency, including the tombstone case."""

    async def _complete_an_import(self, service, stored_file_service, session, client_id):
        """Stage a document and mark its import COMPLETED, as a real import would."""
        staged = await _stage(service, session, client_id=client_id)
        file_import = await session.get(service.entity_class, staged.file_import_id)
        file_import.status_id = FILE_IMPORT_STATUS_COMPLETED
        await session.commit()
        return staged

    @pytest.mark.asyncio
    async def test_duplicate_is_skipped_and_the_orphan_purged(self, file_management_app_manager):
        """A re-upload of imported content creates a SKIPPED import and purges the object."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                first = await self._complete_an_import(
                    service, stored_file_service, session, client_id
                )

                duplicate_key = f"{client_id}/USER_IMPORT_FILE/2026/01/02/{uuid4()}.csv"
                second = await _stage(
                    service, session, client_id=client_id, object_key=duplicate_key
                )

                assert second.is_duplicate is True
                assert second.duplicate_of == first.file_import_id
                assert second.stored_file_id is None

                skipped = await session.get(service.entity_class, second.file_import_id)
                assert skipped.status_id == FILE_IMPORT_STATUS_SKIPPED
                assert skipped.stored_file_id is None
                assert skipped.extra_data["skipped_duplicate_of"] == first.file_import_id

                # No record will ever point at the re-uploaded object: it is purged.
                storage.delete.assert_called_once_with(duplicate_key)

    @pytest.mark.asyncio
    async def test_duplicate_of_a_purged_file_is_still_detected(self, file_management_app_manager):
        """A soft-deleted source file keeps feeding the idempotency lookup."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                first = await self._complete_an_import(
                    service, stored_file_service, session, client_id
                )

                # Purge the source file, as perform_import does after a successful import.
                stored_file = await session.get(
                    stored_file_service.entity_class, first.stored_file_id
                )
                await stored_file_service.soft_delete_file(session, stored_file)
                await session.commit()
                assert stored_file.deleted_at is not None

                second = await _stage(
                    service, session, client_id=client_id,
                    object_key=f"{client_id}/USER_IMPORT_FILE/2026/01/03/{uuid4()}.csv",
                )

                assert second.is_duplicate is True
                assert second.duplicate_of == first.file_import_id

    @pytest.mark.asyncio
    async def test_other_clients_are_not_deduplicated(self, file_management_app_manager):
        """Idempotency is per client: identical content from another client is staged."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                await self._complete_an_import(
                    service, stored_file_service, session, str(uuid4())
                )

                other = await _stage(service, session, client_id=str(uuid4()))
                assert other.is_duplicate is False

    @pytest.mark.asyncio
    async def test_check_idempotency_off_stages_the_duplicate(self, file_management_app_manager):
        """With the check off, the same content is staged again."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                await self._complete_an_import(
                    service, stored_file_service, session, client_id
                )

                again = await _stage(
                    service, session, client_id=client_id, check_idempotency=False
                )
                assert again.is_duplicate is False
                assert again.stored_file_id is not None


class TestFindActiveImportAsync:
    """find_active_import_async: async counterpart of find_active_import."""

    @pytest.mark.asyncio
    async def test_returns_none_on_a_falsy_hash(self, file_management_app_manager):
        service = file_management_app_manager.get_service("file_import")

        async with file_management_app_manager.database.get_session() as session:
            assert await service.find_active_import_async(session, str(uuid4()), "") is None
            assert await service.find_active_import_async(session, str(uuid4()), None) is None

    @pytest.mark.asyncio
    async def test_ignores_failed_imports(self, file_management_app_manager):
        """A failed import must not block a re-import of the same content."""
        service = file_management_app_manager.get_service("file_import")
        stored_file_service = file_management_app_manager.get_service("stored_file")
        storage = _mock_storage()

        with patch.object(stored_file_service, "get_storage_backend", return_value=storage):
            async with file_management_app_manager.database.get_session() as session:
                client_id = str(uuid4())
                staged = await _stage(service, session, client_id=client_id)

                file_import = await session.get(service.entity_class, staged.file_import_id)
                file_import.status_id = "FAILED"
                await session.commit()

                found = await service.find_active_import_async(
                    session, client_id, hashlib.sha256(CONTENT).hexdigest()
                )
                assert found is None
