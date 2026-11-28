"""
Spreadsheet table detection: an .xlsx workbook -> the tables of each sheet, described.

Deterministic and content-agnostic, in the spirit of a dataframe description: for every table, its range,
its title, its header rows and column labels, its label column, the dominant type of each column, and a
nature (time series, record list, key/value block, other) read from that structure. Cell values are not
returned: a caller reads the ranges it needs.

Built on openpyxl only. Plain functions, no app state: usable from any process.

CALLER RESPONSIBILITIES: like ``lys.core.utils.ingest``, this module trusts its input. The workbook is
loaded fully in memory; a caller exposing user uploads bounds the file size (and its uncompressed size)
upstream.
"""
from lys.core.utils.spreadsheet.detection import (
    WorkbookSource,
    detect_sheet_tables,
    detect_tables,
    detect_workbook_tables,
)
from lys.core.utils.spreadsheet.models import (
    CellRange,
    CellType,
    CellValue,
    DetectedTable,
    DetectionOptions,
    RowLabel,
    SequenceKind,
    SequenceOrientation,
    SequenceRun,
    SheetKind,
    SheetNote,
    SheetTables,
    TableColumn,
    TableNature,
    TableSource,
    WorkbookTables,
)

__all__ = [
    "CellRange",
    "CellType",
    "CellValue",
    "DetectedTable",
    "DetectionOptions",
    "RowLabel",
    "SequenceKind",
    "SequenceOrientation",
    "SequenceRun",
    "SheetKind",
    "SheetNote",
    "SheetTables",
    "TableColumn",
    "TableNature",
    "TableSource",
    "WorkbookSource",
    "WorkbookTables",
    "detect_sheet_tables",
    "detect_tables",
    "detect_workbook_tables",
]
