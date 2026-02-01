"""
Unit tests for file_management file_import module constants.

Tests constant definitions and values.
"""

import pytest


class TestFileImportStatusConstants:
    """Tests for FileImport status constants."""

    def test_pending_status(self):
        """Test FILE_IMPORT_STATUS_PENDING is defined."""
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_PENDING
        assert FILE_IMPORT_STATUS_PENDING == "PENDING"

    def test_processing_status(self):
        """Test FILE_IMPORT_STATUS_PROCESSING is defined."""
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_PROCESSING
        assert FILE_IMPORT_STATUS_PROCESSING == "PROCESSING"

    def test_completed_status(self):
        """Test FILE_IMPORT_STATUS_COMPLETED is defined."""
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_COMPLETED
        assert FILE_IMPORT_STATUS_COMPLETED == "COMPLETED"

    def test_failed_status(self):
        """Test FILE_IMPORT_STATUS_FAILED is defined."""
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_FAILED
        assert FILE_IMPORT_STATUS_FAILED == "FAILED"

    def test_cancelled_status(self):
        """Test FILE_IMPORT_STATUS_CANCELLED is defined."""
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_CANCELLED
        assert FILE_IMPORT_STATUS_CANCELLED == "CANCELLED"


class TestReportStatusConstants:
    """Tests for report status constants."""

    def test_error_status(self):
        """Test REPORT_STATUS_ERROR is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_STATUS_ERROR
        assert REPORT_STATUS_ERROR == "ERROR"

    def test_warning_status(self):
        """Test REPORT_STATUS_WARNING is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_STATUS_WARNING
        assert REPORT_STATUS_WARNING == "WARNING"


class TestReportMessageConstants:
    """Tests for report message type constants."""

    def test_missing_message(self):
        """Test REPORT_MESSAGE_MISSING is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_MISSING
        assert REPORT_MESSAGE_MISSING == "MISSING"

    def test_unknown_message(self):
        """Test REPORT_MESSAGE_UNKNOWN is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_UNKNOWN
        assert REPORT_MESSAGE_UNKNOWN == "UNKNOWN"

    def test_wrong_format_message(self):
        """Test REPORT_MESSAGE_WRONG_FORMAT is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_WRONG_FORMAT
        assert REPORT_MESSAGE_WRONG_FORMAT == "WRONG_FORMAT"

    def test_wrong_mime_type_message(self):
        """Test REPORT_MESSAGE_WRONG_MIME_TYPE is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_WRONG_MIME_TYPE
        assert REPORT_MESSAGE_WRONG_MIME_TYPE == "WRONG_MIME_TYPE"

    def test_no_file_message(self):
        """Test REPORT_MESSAGE_NO_FILE is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_NO_FILE
        assert REPORT_MESSAGE_NO_FILE == "NO_FILE"

    def test_internal_error_message(self):
        """Test REPORT_MESSAGE_INTERNAL_ERROR is defined."""
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_INTERNAL_ERROR
        assert REPORT_MESSAGE_INTERNAL_ERROR == "INTERNAL_ERROR"


class TestMimeTypeConstants:
    """Tests for MIME type constants."""

    def test_csv_mime_type(self):
        """Test CSV_MIME_TYPE is defined."""
        from lys.apps.file_management.modules.file_import.consts import CSV_MIME_TYPE
        assert CSV_MIME_TYPE == "text/csv"

    def test_xls_mime_type(self):
        """Test XLS_MIME_TYPE is defined."""
        from lys.apps.file_management.modules.file_import.consts import XLS_MIME_TYPE
        assert XLS_MIME_TYPE == "application/vnd.ms-excel"

    def test_xlsx_mime_type(self):
        """Test XLSX_MIME_TYPE is defined."""
        from lys.apps.file_management.modules.file_import.consts import XLSX_MIME_TYPE
        assert XLSX_MIME_TYPE == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class TestConstantsConsistency:
    """Tests for constants consistency."""

    def test_all_statuses_are_uppercase(self):
        """Test all status constants are uppercase."""
        from lys.apps.file_management.modules.file_import import consts

        statuses = [
            consts.FILE_IMPORT_STATUS_PENDING,
            consts.FILE_IMPORT_STATUS_PROCESSING,
            consts.FILE_IMPORT_STATUS_COMPLETED,
            consts.FILE_IMPORT_STATUS_FAILED,
            consts.FILE_IMPORT_STATUS_CANCELLED,
        ]

        for status in statuses:
            assert status == status.upper()

    def test_all_statuses_are_unique(self):
        """Test all status constants are unique."""
        from lys.apps.file_management.modules.file_import import consts

        statuses = [
            consts.FILE_IMPORT_STATUS_PENDING,
            consts.FILE_IMPORT_STATUS_PROCESSING,
            consts.FILE_IMPORT_STATUS_COMPLETED,
            consts.FILE_IMPORT_STATUS_FAILED,
            consts.FILE_IMPORT_STATUS_CANCELLED,
        ]

        assert len(statuses) == len(set(statuses))
