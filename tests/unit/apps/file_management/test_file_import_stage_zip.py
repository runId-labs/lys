"""
Unit tests for FileImportService.stage_zip_documents() and find_active_import().

stage_zip_documents drives sync sessions and the storage backend; the project does
not integration-test sync-session code on sqlite (async and sync :memory: engines are
distinct databases), so it is covered here with mocks following the same pattern as
test_file_import_services_logic.py.
"""
import zipfile
from unittest.mock import Mock, patch

import pytest

from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_SKIPPED,
)
from lys.apps.file_management.modules.file_import.services import FileImportService
from lys.core.utils.zip import ZipExtractionError

EXTRACT_PATH = "lys.apps.file_management.modules.file_import.services.extract_zip_files"


class _FakeFileImport:
    """Stand-in for the FileImport entity: stores ctor kwargs, auto-assigns an id."""
    _counter = 0

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        _FakeFileImport._counter += 1
        self.id = f"fi-{_FakeFileImport._counter}"


class _FakeStoredFile:
    """Stand-in for the StoredFile entity class (only used as a marker for session.get)."""


def _make_app_manager(zip_file=None):
    """Build a mocked app_manager + sync session + stored_file_service.

    Returns (app_manager, session, stored_file_service). The stored_file_service:
      - download_sync -> raw zip bytes
      - content_hash(data) -> "hash-of-<decoded bytes>" (same content => same hash)
      - upload_sync -> a Mock StoredFile with a unique id, recording every call
    """
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)

    if zip_file is None:
        zip_file = Mock()
        zip_file.client_id = "client-1"
        zip_file.id = "zip-1"
    session.get.return_value = zip_file

    stored_file_service = Mock()
    stored_file_service.entity_class = _FakeStoredFile
    stored_file_service.download_sync.return_value = b"<zip-bytes>"
    stored_file_service.content_hash.side_effect = lambda data: f"hash-of-{data.decode()}"

    uploaded = []

    def _upload_sync(**kwargs):
        uploaded.append(kwargs)
        sf = Mock()
        sf.id = f"sf-{len(uploaded)}"
        return sf

    stored_file_service.upload_sync.side_effect = _upload_sync
    stored_file_service.uploaded_calls = uploaded

    app_manager = Mock()
    app_manager.database.get_sync_session.return_value = session
    app_manager.get_service.side_effect = lambda name: {"stored_file": stored_file_service}[name]
    app_manager.get_entity.side_effect = lambda name: {
        "file_import": _FakeFileImport,
        "stored_file": _FakeStoredFile,
    }[name]
    return app_manager, session, stored_file_service


@pytest.fixture
def staged_env():
    """Provide a configured FileImportService bound to a mocked app_manager.

    Yields (app_manager, session, stored_file_service); resets the test app_manager
    afterwards so the binding does not leak into other tests.
    """
    app_manager, session, stored_file_service = _make_app_manager()
    FileImportService.configure_app_manager_for_testing(app_manager)
    try:
        yield app_manager, session, stored_file_service
    finally:
        FileImportService._app_manager = None


def _added_entities(session):
    """Entities passed to session.add(), in call order."""
    return [call.args[0] for call in session.add.call_args_list]


class TestStageZipDocuments:
    """Tests for the generic ZIP staging engine."""

    def test_stages_each_document(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, return_value=[("a.txt", b"AAA"), ("b.txt", b"BBB")]):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")

        assert result["zip_file_id"] == "zip-1"
        assert len(result["staged"]) == 2
        assert result["skipped"] == []
        assert result["errors"] == []
        assert stored_file_service.upload_sync.call_count == 2
        imports = [e for e in _added_entities(session) if isinstance(e, _FakeFileImport)]
        assert all(fi.status_id == FILE_IMPORT_STATUS_PENDING for fi in imports)
        assert all(fi.type_id == "DSN_IMPORT" for fi in imports)

    def test_deletes_zip_when_no_errors(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, return_value=[("a.txt", b"AAA")]):
            FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        stored_file_service.delete_file_sync.assert_called_once()

    def test_zip_not_deleted_when_errors(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        stored_file_service.upload_sync.side_effect = RuntimeError("upload boom")
        with patch(EXTRACT_PATH, return_value=[("a.txt", b"AAA")]):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert result["errors"]
        stored_file_service.delete_file_sync.assert_not_called()

    def test_zip_file_not_found(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        session.get.return_value = None
        with patch(EXTRACT_PATH) as extract:
            result = FileImportService.stage_zip_documents(
                "missing", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert any("StoredFile not found" in e for e in result["errors"])
        extract.assert_not_called()

    def test_bad_zip_returns_error(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, side_effect=zipfile.BadZipFile("corrupt")):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert any("ZIP extraction failed" in e for e in result["errors"])
        assert result["staged"] == []
        stored_file_service.delete_file_sync.assert_not_called()

    def test_extraction_error_returns_error(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, side_effect=ZipExtractionError("too many files")):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert any("ZIP extraction failed" in e for e in result["errors"])

    def test_max_files_forwarded_to_extractor(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, side_effect=ZipExtractionError("too many")) as extract:
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT", max_files=2)
        # max_files is enforced DURING extraction, not post-hoc.
        assert extract.call_args.kwargs.get("max_files") == 2
        assert result["errors"]

    def test_max_files_none_not_forwarded(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, return_value=[("a.txt", b"AAA")]) as extract:
            FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert "max_files" not in extract.call_args.kwargs

    def test_per_document_error_isolation(self, staged_env):
        app_manager, session, stored_file_service = staged_env

        def _upload(**kwargs):
            if kwargs["original_name"] == "bad.txt":
                raise RuntimeError("upload failed")
            sf = Mock()
            sf.id = "sf-ok"
            return sf

        stored_file_service.upload_sync.side_effect = _upload
        with patch(EXTRACT_PATH, return_value=[("good.txt", b"AAA"), ("bad.txt", b"BBB")]):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert len(result["staged"]) == 1
        assert len(result["errors"]) == 1
        assert "bad.txt" in result["errors"][0]

    def test_outer_failure_caught(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        stored_file_service.download_sync.side_effect = RuntimeError("download died")
        result = FileImportService.stage_zip_documents(
            "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT")
        assert any("Failed to process ZIP" in e for e in result["errors"])

    def test_callables_forwarded(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, return_value=[("doc.xml", b"AAA")]):
            FileImportService.stage_zip_documents(
                "zip-1",
                per_file_type_id="DOC",
                import_type_id="DSN_IMPORT",
                mime_resolver=lambda name: "application/xml",
                per_file_extra_data=lambda zf, name: {"kind": "dsn"},
                stored_file_fields=lambda zf, name: {"campaign_id": "c-9"},
                file_import_fields=lambda zf, name: {"period": "2026-06"},
            )
        upload_kwargs = stored_file_service.uploaded_calls[0]
        assert upload_kwargs["mime_type"] == "application/xml"
        assert upload_kwargs["extra_data"] == {"kind": "dsn"}
        assert upload_kwargs["campaign_id"] == "c-9"
        imports = [e for e in _added_entities(session) if isinstance(e, _FakeFileImport)]
        assert imports[0].period == "2026-06"
        assert imports[0].extra_data == {"kind": "dsn"}


class TestStageZipIdempotency:
    """Content-hash idempotency behaviour inside stage_zip_documents."""

    def test_skips_existing_db_duplicate(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        existing = Mock()
        existing.id = "existing-1"
        with patch(EXTRACT_PATH, return_value=[("a.txt", b"AAA")]), \
                patch.object(FileImportService, "find_active_import", return_value=existing):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT",
                check_idempotency=True)
        assert result["staged"] == []
        assert result["skipped"] == [{"name": "a.txt", "duplicate_of": "existing-1"}]
        stored_file_service.upload_sync.assert_not_called()
        skipped = [e for e in _added_entities(session) if isinstance(e, _FakeFileImport)][0]
        assert skipped.status_id == FILE_IMPORT_STATUS_SKIPPED
        assert skipped.stored_file_id is None
        assert skipped.extra_data["skipped_duplicate_of"] == "existing-1"
        assert skipped.extra_data["content_hash"] == "hash-of-AAA"
        assert skipped.extra_data["original_file_name"] == "a.txt"

    def test_skips_in_batch_duplicate(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        # Same content twice; nothing in DB.
        with patch(EXTRACT_PATH, return_value=[("first.txt", b"AAA"), ("second.txt", b"AAA")]), \
                patch.object(FileImportService, "find_active_import", return_value=None):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT",
                check_idempotency=True)
        assert len(result["staged"]) == 1
        assert len(result["skipped"]) == 1
        first_id = result["staged"][0]
        assert result["skipped"][0]["duplicate_of"] == first_id
        stored_file_service.upload_sync.assert_called_once()

    def test_in_batch_original_preferred_over_db(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        db_existing = Mock()
        db_existing.id = "db-existing"
        # First call (first.txt): no active DB import -> staged. Second call (second.txt,
        # same content): a DB import exists, but the in-batch original must win.
        with patch(EXTRACT_PATH, return_value=[("first.txt", b"AAA"), ("second.txt", b"AAA")]), \
                patch.object(FileImportService, "find_active_import",
                             side_effect=[None, db_existing]):
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT",
                check_idempotency=True)
        first_id = result["staged"][0]
        assert result["skipped"][0]["duplicate_of"] == first_id
        assert result["skipped"][0]["duplicate_of"] != "db-existing"

    def test_idempotency_disabled_imports_duplicates(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        with patch(EXTRACT_PATH, return_value=[("a.txt", b"AAA"), ("b.txt", b"AAA")]), \
                patch.object(FileImportService, "find_active_import") as find:
            result = FileImportService.stage_zip_documents(
                "zip-1", per_file_type_id="DOC", import_type_id="DSN_IMPORT",
                check_idempotency=False)
        assert len(result["staged"]) == 2
        assert result["skipped"] == []
        find.assert_not_called()


class TestFindActiveImport:
    """Tests for find_active_import guard clauses (query execution is integration-level)."""

    def test_returns_none_for_empty_hash(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        assert FileImportService.find_active_import(session, "client-1", "") is None
        session.execute.assert_not_called()

    def test_returns_none_for_none_hash(self, staged_env):
        app_manager, session, stored_file_service = staged_env
        assert FileImportService.find_active_import(session, "client-1", None) is None
        session.execute.assert_not_called()
