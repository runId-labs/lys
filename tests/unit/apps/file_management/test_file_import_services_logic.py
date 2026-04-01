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


class TestPerformImportReRaises:
    """Tests that perform_import re-raises exceptions after updating status."""

    def test_reraises_exception_on_import_failure(self):
        """Test that perform_import re-raises after setting FAILED status."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        import pytest

        mock_file_import = Mock()
        mock_file_import.stored_file = Mock()
        mock_file_import.config = None

        mock_session = Mock()
        mock_session.get.return_value = mock_file_import
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)

        mock_file_import_service = Mock()
        mock_file_import_service.entity_class = Mock

        mock_stored_file_service = Mock()
        mock_stored_file_service.download_sync.side_effect = RuntimeError("download failed")

        mock_app_manager = Mock()
        mock_app_manager.database.get_sync_session.return_value = mock_session
        mock_app_manager.get_service.side_effect = lambda name: {
            "file_import": mock_file_import_service,
            "stored_file": mock_stored_file_service,
        }[name]

        # Create a concrete subclass for testing
        class ConcreteImportService(AbstractImportService):
            import_type = "TEST"
            unique_column = "id"

            def get_column_mapping(self):
                return {}

            def init_entity(self, unique_value, session):
                return Mock()

        service = ConcreteImportService(mock_app_manager)

        with pytest.raises(RuntimeError, match="download failed"):
            service.perform_import("test-id")

        # Verify status was updated to FAILED before re-raising
        mock_file_import_service.update_progress.assert_called_once()
        call_args = mock_file_import_service.update_progress.call_args
        assert call_args[0][1] == "FAILED"
        mock_session.commit.assert_called_once()
