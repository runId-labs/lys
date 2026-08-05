"""
Unit tests for StoredFileService._remove_file_sync() and its two public wrappers
(delete_file_sync / soft_delete_file_sync).

These methods drive sync sessions; the project does not integration-test sync-session
code on sqlite (async and sync :memory: engines are distinct databases), so they are
covered here with mocks following the pattern of test_file_import_stage_zip.py.
"""
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from lys.apps.file_management.modules.stored_file.services import StoredFileService


class _FakeStoredFile:
    """Stand-in for a StoredFile row: only the fields the deletion path touches."""

    def __init__(self, file_id="sf-1", object_key="client/TYPE/2024/01/01/file.csv", deleted_at=None):
        self.id = file_id
        self.object_key = object_key
        self.deleted_at = deleted_at

    @property
    def path(self):
        return self.object_key


@pytest.fixture
def delete_env():
    """Mocked app_manager + sync session + storage backend bound to StoredFileService.

    Yields (session, storage, db_row_holder) where db_row_holder is a one-element list
    holding what ``session.get`` returns (None to simulate a row already deleted).
    """
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)

    db_row_holder = [None]
    session.get.side_effect = lambda entity_class, file_id: db_row_holder[0]

    app_manager = Mock()
    app_manager.database.get_sync_session.return_value = session

    storage = Mock()

    with patch.object(StoredFileService, "app_manager", app_manager, create=True), \
            patch.object(StoredFileService, "entity_class", _FakeStoredFile, create=True), \
            patch.object(StoredFileService, "get_storage_backend", return_value=storage):
        yield session, storage, db_row_holder


class TestSoftDeleteFileSync:
    """soft_delete_file_sync: purge the S3 bytes, keep the row as a tombstone."""

    def test_purges_bytes_and_marks_row(self, delete_env):
        session, storage, db_row = delete_env
        row = _FakeStoredFile()
        db_row[0] = row

        StoredFileService.soft_delete_file_sync(_FakeStoredFile())

        storage.delete_sync.assert_called_once_with(row.path)
        assert isinstance(row.deleted_at, datetime)
        assert row.deleted_at.tzinfo is not None
        session.delete.assert_not_called()  # the row is kept as a tombstone
        session.commit.assert_called_once()

    def test_is_a_no_op_on_an_existing_tombstone(self, delete_env):
        session, storage, db_row = delete_env
        already_purged = datetime(2026, 1, 1, 12, 0)
        db_row[0] = _FakeStoredFile(deleted_at=already_purged)

        StoredFileService.soft_delete_file_sync(_FakeStoredFile())

        storage.delete_sync.assert_not_called()
        session.commit.assert_not_called()
        assert db_row[0].deleted_at == already_purged  # timestamp not refreshed

    def test_purges_bytes_when_the_row_is_already_gone(self, delete_env):
        session, storage, db_row = delete_env
        db_row[0] = None
        detached = _FakeStoredFile(object_key="orphan/key.csv")

        StoredFileService.soft_delete_file_sync(detached)

        # No row to mark, but the bytes must not be left orphaned in S3.
        storage.delete_sync.assert_called_once_with("orphan/key.csv")
        session.commit.assert_not_called()

    def test_rolls_back_and_reraises_on_storage_failure(self, delete_env):
        session, storage, db_row = delete_env
        db_row[0] = _FakeStoredFile()
        storage.delete_sync.side_effect = RuntimeError("S3 unreachable")

        with pytest.raises(RuntimeError, match="S3 unreachable"):
            StoredFileService.soft_delete_file_sync(_FakeStoredFile())

        session.rollback.assert_called_once()
        session.commit.assert_not_called()
        assert db_row[0].deleted_at is None

    def test_rolls_back_and_reraises_on_commit_failure(self, delete_env):
        session, storage, db_row = delete_env
        db_row[0] = _FakeStoredFile()
        session.commit.side_effect = RuntimeError("DB gone")

        with pytest.raises(RuntimeError, match="DB gone"):
            StoredFileService.soft_delete_file_sync(_FakeStoredFile())

        session.rollback.assert_called_once()
        # Documented trade-off: the purge runs before the commit, so on a commit failure
        # the bytes are gone while the row stays unmarked (only a new call fixes it).
        storage.delete_sync.assert_called_once()


class TestDeleteFileSync:
    """delete_file_sync: hard delete — purge the S3 bytes and drop the row."""

    def test_purges_bytes_and_deletes_row(self, delete_env):
        session, storage, db_row = delete_env
        row = _FakeStoredFile()
        db_row[0] = row

        StoredFileService.delete_file_sync(_FakeStoredFile())

        storage.delete_sync.assert_called_once_with(row.path)
        session.delete.assert_called_once_with(row)
        session.commit.assert_called_once()
        assert row.deleted_at is None  # hard delete does not tombstone

    def test_purges_bytes_when_the_row_is_already_gone(self, delete_env):
        session, storage, db_row = delete_env
        db_row[0] = None

        StoredFileService.delete_file_sync(_FakeStoredFile(object_key="orphan/key.csv"))

        storage.delete_sync.assert_called_once_with("orphan/key.csv")
        session.delete.assert_not_called()
        session.commit.assert_not_called()

    def test_ignores_the_tombstone_guard(self, delete_env):
        """A tombstoned row is still hard-deletable (the guard is soft-only)."""
        session, storage, db_row = delete_env
        row = _FakeStoredFile(deleted_at=datetime(2026, 1, 1, 12, 0))
        db_row[0] = row

        StoredFileService.delete_file_sync(_FakeStoredFile())

        storage.delete_sync.assert_called_once()
        session.delete.assert_called_once_with(row)
        session.commit.assert_called_once()
