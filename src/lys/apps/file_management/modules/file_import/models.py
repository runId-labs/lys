"""
Import models for file import processing.

These are Python classes (not database entities) used to describe
import configuration and track import results.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Optional

from sqlalchemy.orm import Session

from lys.apps.file_management.modules.file_import.consts import (
    REPORT_STATUS_ERROR,
    REPORT_STATUS_WARNING,
    REPORT_MESSAGE_MISSING,
    REPORT_MESSAGE_UNKNOWN,
    REPORT_MESSAGE_WRONG_FORMAT,
    REPORT_MESSAGE_INTERNAL_ERROR,
)
from lys.core.entities import Entity


@dataclass
class ImportColumn:
    """
    Describes how to import a single column from the file.

    Attributes:
        is_optional: Whether this column is required in the import file
        validator: Function to validate the cell value, returns True if valid
        setter: Function to set the value on the entity
    """
    is_optional: bool
    validator: Callable[[Any], bool]
    setter: Callable[[Entity, Any, Session], None]


@dataclass
class ImportMessage:
    """
    A single import message (error or warning).

    Attributes:
        status: ERROR or WARNING
        message: Message type (MISSING, WRONG_FORMAT, etc.)
        details: Optional additional details
    """
    status: str
    message: str
    details: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        result = {"status": self.status, "message": self.message}
        if self.details:
            result["details"] = self.details
        return result

    @classmethod
    def error(cls, message: str, details: Optional[str] = None) -> "ImportMessage":
        return cls(status=REPORT_STATUS_ERROR, message=message, details=details)

    @classmethod
    def warning(cls, message: str, details: Optional[str] = None) -> "ImportMessage":
        return cls(status=REPORT_STATUS_WARNING, message=message, details=details)

    @classmethod
    def missing(cls) -> "ImportMessage":
        return cls.error(REPORT_MESSAGE_MISSING)

    @classmethod
    def unknown(cls) -> "ImportMessage":
        return cls.warning(REPORT_MESSAGE_UNKNOWN)

    @classmethod
    def wrong_format(cls, details: Optional[str] = None) -> "ImportMessage":
        return cls.error(REPORT_MESSAGE_WRONG_FORMAT, details)

    @classmethod
    def internal_error(cls, details: str) -> "ImportMessage":
        return cls.error(REPORT_MESSAGE_INTERNAL_ERROR, details)


@dataclass
class ImportReport:
    """
    Complete import report with errors and warnings.

    Attributes:
        has_blocking_error: True if import cannot proceed due to errors
        globals: Global errors (file issues, etc.)
        headers: Errors/warnings per column header
        rows: Errors/warnings per row and column
    """
    has_blocking_error: bool = False
    globals: list[ImportMessage] = field(default_factory=list)
    headers: dict[str, ImportMessage] = field(default_factory=dict)
    rows: dict[Hashable, dict[str, ImportMessage]] = field(default_factory=dict)

    def add_global_error(self, message: str, details: Optional[str] = None) -> None:
        """Add a global error and mark as blocking."""
        self.globals.append(ImportMessage.error(message, details))
        self.has_blocking_error = True

    def add_global_warning(self, message: str, details: Optional[str] = None) -> None:
        """Add a global warning (non-blocking)."""
        self.globals.append(ImportMessage.warning(message, details))

    def add_header_error(self, header: str, message: ImportMessage) -> None:
        """Add a header-level error."""
        self.headers[header] = message
        if message.status == REPORT_STATUS_ERROR:
            self.has_blocking_error = True

    def add_row_error(
        self,
        row_index: Hashable,
        column: str,
        message: ImportMessage
    ) -> None:
        """Add a row-level error for a specific column."""
        if row_index not in self.rows:
            self.rows[row_index] = {}
        self.rows[row_index][column] = message

    @property
    def error_count(self) -> int:
        """Total number of row errors."""
        return sum(len(cols) for cols in self.rows.values())

    @property
    def success_count(self) -> int:
        """This should be set externally based on processed rows."""
        return 0

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "has_blocking_error": self.has_blocking_error,
            "globals": [msg.to_dict() for msg in self.globals],
            "headers": {k: v.to_dict() for k, v in self.headers.items()},
            "rows": {
                str(k): {col: msg.to_dict() for col, msg in cols.items()}
                for k, cols in self.rows.items()
            },
        }


@dataclass
class ImportConfig:
    """
    Configuration for an import job.

    Attributes:
        skip_header: Whether to skip the first row (header)
        delimiter: CSV delimiter character
        encoding: File encoding
        mapping: Optional column mapping {target_field: source_column}
    """
    skip_header: bool = True
    delimiter: str = ","
    encoding: str = "utf-8"
    mapping: Optional[dict[str, str]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skip_header": self.skip_header,
            "delimiter": self.delimiter,
            "encoding": self.encoding,
            "mapping": self.mapping,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImportConfig":
        return cls(
            skip_header=data.get("skip_header", True),
            delimiter=data.get("delimiter", ","),
            encoding=data.get("encoding", "utf-8"),
            mapping=data.get("mapping"),
        )