"""
Unit tests for FileImportService.update_progress() logic.
"""
from unittest.mock import Mock, patch


class TestUpdateProgress:
    """Tests for FileImportService.update_progress() — in-place mutation, no DB."""

    def _make_file_import(self):
        mock = Mock()
        mock.status_id = "PENDING"
        mock.errors = None
        mock.total_rows = None
        mock.processed_rows = None
        mock.success_rows = None
        mock.error_rows = None
        mock.started_at = None
        mock.completed_at = None
        return mock

    def test_sets_status(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        FileImportService.update_progress(fi, "PROCESSING")
        assert fi.status_id == "PROCESSING"

    def test_sets_report(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        from lys.apps.file_management.modules.file_import.models import ImportReport
        fi = self._make_file_import()
        report = ImportReport()
        report.add_global_error("NO_FILE")
        FileImportService.update_progress(fi, "FAILED", report=report)
        assert fi.errors["has_blocking_error"] is True

    def test_sets_total_rows(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        FileImportService.update_progress(fi, "PROCESSING", total_rows=100)
        assert fi.total_rows == 100

    def test_sets_processed_and_success_rows(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        FileImportService.update_progress(
            fi, "PROCESSING", processed_rows=50, success_rows=45, error_rows=5
        )
        assert fi.processed_rows == 50
        assert fi.success_rows == 45
        assert fi.error_rows == 5

    def test_started_at_set_on_first_processing(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        fi.started_at = None
        FileImportService.update_progress(fi, "PROCESSING")
        assert fi.started_at is not None

    def test_started_at_not_overwritten(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        original_started = "2024-01-01T00:00:00"
        fi.started_at = original_started
        FileImportService.update_progress(fi, "PROCESSING")
        assert fi.started_at == original_started

    def test_completed_at_set_on_completed(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        FileImportService.update_progress(fi, "COMPLETED")
        assert fi.completed_at is not None

    def test_completed_at_set_on_failed(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        FileImportService.update_progress(fi, "FAILED")
        assert fi.completed_at is not None

    def test_completed_at_not_set_on_processing(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        FileImportService.update_progress(fi, "PROCESSING")
        assert fi.completed_at is None

    def test_none_report_does_not_overwrite(self):
        from lys.apps.file_management.modules.file_import.services import FileImportService
        fi = self._make_file_import()
        fi.errors = {"old": "data"}
        FileImportService.update_progress(fi, "PROCESSING", report=None)
        assert fi.errors == {"old": "data"}
