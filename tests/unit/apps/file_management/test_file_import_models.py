"""
Unit tests for file_management file_import module models.

Tests dataclass structure and methods.
"""

import pytest


class TestImportColumn:
    """Tests for ImportColumn dataclass."""

    def test_class_exists(self):
        """Test ImportColumn class exists."""
        from lys.apps.file_management.modules.file_import.models import ImportColumn
        assert ImportColumn is not None

    def test_is_dataclass(self):
        """Test ImportColumn is a dataclass."""
        from dataclasses import is_dataclass
        from lys.apps.file_management.modules.file_import.models import ImportColumn
        assert is_dataclass(ImportColumn)

    def test_has_is_optional_field(self):
        """Test ImportColumn has is_optional field."""
        from lys.apps.file_management.modules.file_import.models import ImportColumn
        assert hasattr(ImportColumn, "__dataclass_fields__")
        assert "is_optional" in ImportColumn.__dataclass_fields__

    def test_has_validator_field(self):
        """Test ImportColumn has validator field."""
        from lys.apps.file_management.modules.file_import.models import ImportColumn
        assert "validator" in ImportColumn.__dataclass_fields__

    def test_has_setter_field(self):
        """Test ImportColumn has setter field."""
        from lys.apps.file_management.modules.file_import.models import ImportColumn
        assert "setter" in ImportColumn.__dataclass_fields__

    def test_can_create_instance(self):
        """Test can create ImportColumn instance."""
        from lys.apps.file_management.modules.file_import.models import ImportColumn

        column = ImportColumn(
            is_optional=False,
            validator=lambda x: True,
            setter=lambda e, v, s: None,
        )
        assert column.is_optional is False


class TestImportMessage:
    """Tests for ImportMessage dataclass."""

    def test_class_exists(self):
        """Test ImportMessage class exists."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        assert ImportMessage is not None

    def test_is_dataclass(self):
        """Test ImportMessage is a dataclass."""
        from dataclasses import is_dataclass
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        assert is_dataclass(ImportMessage)

    def test_has_status_field(self):
        """Test ImportMessage has status field."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        assert "status" in ImportMessage.__dataclass_fields__

    def test_has_message_field(self):
        """Test ImportMessage has message field."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        assert "message" in ImportMessage.__dataclass_fields__

    def test_has_details_field(self):
        """Test ImportMessage has details field."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        assert "details" in ImportMessage.__dataclass_fields__

    def test_to_dict_method(self):
        """Test ImportMessage to_dict method."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage

        msg = ImportMessage(status="ERROR", message="TEST", details="detail")
        result = msg.to_dict()
        assert result["status"] == "ERROR"
        assert result["message"] == "TEST"
        assert result["details"] == "detail"

    def test_to_dict_without_details(self):
        """Test ImportMessage to_dict without details."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage

        msg = ImportMessage(status="ERROR", message="TEST")
        result = msg.to_dict()
        assert "details" not in result

    def test_error_classmethod(self):
        """Test ImportMessage.error classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        from lys.apps.file_management.modules.file_import.consts import REPORT_STATUS_ERROR

        msg = ImportMessage.error("TEST")
        assert msg.status == REPORT_STATUS_ERROR
        assert msg.message == "TEST"

    def test_warning_classmethod(self):
        """Test ImportMessage.warning classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        from lys.apps.file_management.modules.file_import.consts import REPORT_STATUS_WARNING

        msg = ImportMessage.warning("TEST")
        assert msg.status == REPORT_STATUS_WARNING
        assert msg.message == "TEST"

    def test_missing_classmethod(self):
        """Test ImportMessage.missing classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_MISSING

        msg = ImportMessage.missing()
        assert msg.message == REPORT_MESSAGE_MISSING

    def test_unknown_classmethod(self):
        """Test ImportMessage.unknown classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_UNKNOWN

        msg = ImportMessage.unknown()
        assert msg.message == REPORT_MESSAGE_UNKNOWN

    def test_wrong_format_classmethod(self):
        """Test ImportMessage.wrong_format classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_WRONG_FORMAT

        msg = ImportMessage.wrong_format("invalid value")
        assert msg.message == REPORT_MESSAGE_WRONG_FORMAT
        assert msg.details == "invalid value"

    def test_internal_error_classmethod(self):
        """Test ImportMessage.internal_error classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportMessage
        from lys.apps.file_management.modules.file_import.consts import REPORT_MESSAGE_INTERNAL_ERROR

        msg = ImportMessage.internal_error("exception details")
        assert msg.message == REPORT_MESSAGE_INTERNAL_ERROR
        assert msg.details == "exception details"


class TestImportReport:
    """Tests for ImportReport dataclass."""

    def test_class_exists(self):
        """Test ImportReport class exists."""
        from lys.apps.file_management.modules.file_import.models import ImportReport
        assert ImportReport is not None

    def test_is_dataclass(self):
        """Test ImportReport is a dataclass."""
        from dataclasses import is_dataclass
        from lys.apps.file_management.modules.file_import.models import ImportReport
        assert is_dataclass(ImportReport)

    def test_default_has_blocking_error_is_false(self):
        """Test default has_blocking_error is False."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        assert report.has_blocking_error is False

    def test_default_globals_is_empty_list(self):
        """Test default globals is empty list."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        assert report.globals == []

    def test_default_headers_is_empty_dict(self):
        """Test default headers is empty dict."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        assert report.headers == {}

    def test_default_rows_is_empty_dict(self):
        """Test default rows is empty dict."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        assert report.rows == {}

    def test_add_global_error_sets_blocking(self):
        """Test add_global_error sets has_blocking_error."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        report.add_global_error("TEST")
        assert report.has_blocking_error is True
        assert len(report.globals) == 1

    def test_add_global_warning_does_not_set_blocking(self):
        """Test add_global_warning does not set has_blocking_error."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        report.add_global_warning("TEST")
        assert report.has_blocking_error is False
        assert len(report.globals) == 1

    def test_add_header_error(self):
        """Test add_header_error method."""
        from lys.apps.file_management.modules.file_import.models import ImportReport, ImportMessage

        report = ImportReport()
        report.add_header_error("email", ImportMessage.missing())
        assert "email" in report.headers
        assert report.has_blocking_error is True

    def test_add_row_error(self):
        """Test add_row_error method."""
        from lys.apps.file_management.modules.file_import.models import ImportReport, ImportMessage

        report = ImportReport()
        report.add_row_error(0, "email", ImportMessage.wrong_format())
        assert 0 in report.rows
        assert "email" in report.rows[0]

    def test_error_count_property(self):
        """Test error_count property."""
        from lys.apps.file_management.modules.file_import.models import ImportReport, ImportMessage

        report = ImportReport()
        report.add_row_error(0, "email", ImportMessage.wrong_format())
        report.add_row_error(0, "name", ImportMessage.wrong_format())
        report.add_row_error(1, "email", ImportMessage.wrong_format())
        assert report.error_count == 3

    def test_to_dict_method(self):
        """Test to_dict method."""
        from lys.apps.file_management.modules.file_import.models import ImportReport

        report = ImportReport()
        result = report.to_dict()
        assert "has_blocking_error" in result
        assert "globals" in result
        assert "headers" in result
        assert "rows" in result


class TestImportConfig:
    """Tests for ImportConfig dataclass."""

    def test_class_exists(self):
        """Test ImportConfig class exists."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig
        assert ImportConfig is not None

    def test_is_dataclass(self):
        """Test ImportConfig is a dataclass."""
        from dataclasses import is_dataclass
        from lys.apps.file_management.modules.file_import.models import ImportConfig
        assert is_dataclass(ImportConfig)

    def test_default_skip_header_is_true(self):
        """Test default skip_header is True."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        config = ImportConfig()
        assert config.skip_header is True

    def test_default_delimiter_is_comma(self):
        """Test default delimiter is comma."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        config = ImportConfig()
        assert config.delimiter == ","

    def test_default_encoding_is_utf8(self):
        """Test default encoding is utf-8."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        config = ImportConfig()
        assert config.encoding == "utf-8"

    def test_default_mapping_is_none(self):
        """Test default mapping is None."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        config = ImportConfig()
        assert config.mapping is None

    def test_to_dict_method(self):
        """Test to_dict method."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        config = ImportConfig(delimiter=";", encoding="latin-1")
        result = config.to_dict()
        assert result["delimiter"] == ";"
        assert result["encoding"] == "latin-1"
        assert result["skip_header"] is True

    def test_from_dict_classmethod(self):
        """Test from_dict classmethod."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        data = {"delimiter": ";", "encoding": "latin-1", "skip_header": False}
        config = ImportConfig.from_dict(data)
        assert config.delimiter == ";"
        assert config.encoding == "latin-1"
        assert config.skip_header is False

    def test_from_dict_with_defaults(self):
        """Test from_dict with missing keys uses defaults."""
        from lys.apps.file_management.modules.file_import.models import ImportConfig

        config = ImportConfig.from_dict({})
        assert config.delimiter == ","
        assert config.encoding == "utf-8"
        assert config.skip_header is True
