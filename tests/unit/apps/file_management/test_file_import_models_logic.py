"""
Unit tests for file import models (ImportMessage, ImportReport, ImportConfig) — pure logic.
"""
from lys.apps.file_management.modules.file_import.consts import (
    REPORT_STATUS_ERROR,
    REPORT_STATUS_WARNING,
    REPORT_MESSAGE_MISSING,
    REPORT_MESSAGE_UNKNOWN,
    REPORT_MESSAGE_WRONG_FORMAT,
    REPORT_MESSAGE_INTERNAL_ERROR,
)
from lys.apps.file_management.modules.file_import.models import (
    ImportMessage,
    ImportReport,
    ImportConfig,
)


class TestImportMessageFactories:
    """Tests for ImportMessage factory methods."""

    def test_error_factory(self):
        msg = ImportMessage.error("CUSTOM", details="extra")
        assert msg.status == REPORT_STATUS_ERROR
        assert msg.message == "CUSTOM"
        assert msg.details == "extra"

    def test_warning_factory(self):
        msg = ImportMessage.warning("CUSTOM")
        assert msg.status == REPORT_STATUS_WARNING
        assert msg.message == "CUSTOM"
        assert msg.details is None

    def test_missing_factory(self):
        msg = ImportMessage.missing()
        assert msg.status == REPORT_STATUS_ERROR
        assert msg.message == REPORT_MESSAGE_MISSING

    def test_unknown_factory(self):
        msg = ImportMessage.unknown()
        assert msg.status == REPORT_STATUS_WARNING
        assert msg.message == REPORT_MESSAGE_UNKNOWN

    def test_wrong_format_factory(self):
        msg = ImportMessage.wrong_format("bad value")
        assert msg.status == REPORT_STATUS_ERROR
        assert msg.message == REPORT_MESSAGE_WRONG_FORMAT
        assert msg.details == "bad value"

    def test_internal_error_factory(self):
        msg = ImportMessage.internal_error("traceback info")
        assert msg.status == REPORT_STATUS_ERROR
        assert msg.message == REPORT_MESSAGE_INTERNAL_ERROR
        assert msg.details == "traceback info"


class TestImportMessageToDict:
    """Tests for ImportMessage.to_dict()."""

    def test_to_dict_without_details(self):
        msg = ImportMessage(status="ERROR", message="TEST")
        result = msg.to_dict()
        assert result == {"status": "ERROR", "message": "TEST"}
        assert "details" not in result

    def test_to_dict_with_details(self):
        msg = ImportMessage(status="ERROR", message="TEST", details="extra")
        result = msg.to_dict()
        assert result == {"status": "ERROR", "message": "TEST", "details": "extra"}


class TestImportReport:
    """Tests for ImportReport logic."""

    def test_initial_state(self):
        report = ImportReport()
        assert report.has_blocking_error is False
        assert report.globals == []
        assert report.headers == {}
        assert report.rows == {}

    def test_add_global_error_sets_blocking(self):
        report = ImportReport()
        report.add_global_error("NO_FILE", "file not found")
        assert report.has_blocking_error is True
        assert len(report.globals) == 1
        assert report.globals[0].status == REPORT_STATUS_ERROR

    def test_add_global_warning_not_blocking(self):
        report = ImportReport()
        report.add_global_warning("Some warning")
        assert report.has_blocking_error is False
        assert len(report.globals) == 1
        assert report.globals[0].status == REPORT_STATUS_WARNING

    def test_add_header_error_with_error_status_sets_blocking(self):
        report = ImportReport()
        report.add_header_error("email", ImportMessage.missing())
        assert report.has_blocking_error is True
        assert "email" in report.headers

    def test_add_header_error_with_warning_not_blocking(self):
        report = ImportReport()
        report.add_header_error("extra_col", ImportMessage.unknown())
        assert report.has_blocking_error is False
        assert "extra_col" in report.headers

    def test_add_row_error(self):
        report = ImportReport()
        report.add_row_error(0, "email", ImportMessage.wrong_format("bad"))
        assert 0 in report.rows
        assert "email" in report.rows[0]

    def test_error_count(self):
        report = ImportReport()
        report.add_row_error(0, "email", ImportMessage.wrong_format("bad"))
        report.add_row_error(0, "name", ImportMessage.wrong_format("bad"))
        report.add_row_error(1, "email", ImportMessage.wrong_format("bad"))
        assert report.error_count == 3

    def test_error_count_empty(self):
        report = ImportReport()
        assert report.error_count == 0

    def test_to_dict(self):
        report = ImportReport()
        report.add_global_error("NO_FILE")
        report.add_row_error(0, "email", ImportMessage.wrong_format("bad"))
        result = report.to_dict()
        assert result["has_blocking_error"] is True
        assert len(result["globals"]) == 1
        assert "0" in result["rows"]


class TestImportConfig:
    """Tests for ImportConfig to_dict/from_dict roundtrip."""

    def test_default_values(self):
        config = ImportConfig()
        assert config.skip_header is True
        assert config.delimiter == ","
        assert config.encoding == "utf-8"
        assert config.mapping is None

    def test_to_dict(self):
        config = ImportConfig(delimiter=";", encoding="latin-1")
        d = config.to_dict()
        assert d["delimiter"] == ";"
        assert d["encoding"] == "latin-1"

    def test_from_dict(self):
        data = {"skip_header": False, "delimiter": "\t", "encoding": "utf-16", "mapping": {"a": "b"}}
        config = ImportConfig.from_dict(data)
        assert config.skip_header is False
        assert config.delimiter == "\t"
        assert config.encoding == "utf-16"
        assert config.mapping == {"a": "b"}

    def test_roundtrip(self):
        original = ImportConfig(skip_header=False, delimiter=";", encoding="latin-1", mapping={"col1": "A"})
        restored = ImportConfig.from_dict(original.to_dict())
        assert restored.skip_header == original.skip_header
        assert restored.delimiter == original.delimiter
        assert restored.encoding == original.encoding
        assert restored.mapping == original.mapping

    def test_from_dict_defaults(self):
        config = ImportConfig.from_dict({})
        assert config.skip_header is True
        assert config.delimiter == ","
