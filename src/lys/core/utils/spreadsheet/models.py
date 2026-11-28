"""
Output models of the spreadsheet table detector.

Each model describes structure only: where a table sits, what heads it, what type its columns hold,
and how it reads. Cell values are not copied, except the header values. A caller reads the data itself
from the ranges given here.
"""
from datetime import date, datetime, time
from enum import Enum
from typing import Optional, Union

from openpyxl.utils import get_column_letter
from pydantic import BaseModel, ConfigDict, computed_field

#: A header value as the workbook stores it (openpyxl ``data_only`` values)
CellValue = Optional[Union[bool, int, float, datetime, date, time, str]]


class CellType(str, Enum):
    """The dominant type of a column's cells, or the type of one cell."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOL = "bool"
    #: No type holds at least ``DetectionOptions.dominant_share`` of the non-empty cells
    MIXED = "mixed"
    EMPTY = "empty"


class TableNature(str, Enum):
    """How a table reads, derived from its structure once it is detected (never a condition for it)."""
    #: Header cells (or a leading date column) form an ordered sequence: dates, integers, numbered labels
    TIME_SERIES = "time_series"
    #: One row is one record, described by the columns of the header
    RECORD_LIST = "record_list"
    #: A label column and a single value column (text columns such as comments aside)
    KEY_VALUE = "key_value"
    OTHER = "other"


class SheetKind(str, Enum):
    WORKSHEET = "worksheet"
    #: A sheet holding a chart only: no cells, no tables
    CHARTSHEET = "chartsheet"


class TableSource(str, Enum):
    #: An Excel table object (``Insert > Table``), read from ``worksheet.tables``
    NATIVE = "native"
    #: A region of cells found by the detector
    REGION = "region"


class SequenceOrientation(str, Enum):
    #: The sequence runs along a header row, one value per column
    COLUMNS = "columns"
    #: The sequence runs down a column, one value per row
    ROWS = "rows"


class SequenceKind(str, Enum):
    #: Strictly increasing dates
    DATE = "date"
    #: Integers with a constant step (2024, 2025, 2026)
    NUMBER = "number"
    #: Labels identical but for an integer with a constant step ("S1", "S2"; "Week 1", "Week 2")
    NUMBERED_TEXT = "numbered_text"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class CellRange(_Frozen):
    """A rectangle of cells, 1-based and inclusive."""
    min_row: int
    min_col: int
    max_row: int
    max_col: int

    @computed_field
    @property
    def height(self) -> int:
        return self.max_row - self.min_row + 1

    @computed_field
    @property
    def width(self) -> int:
        return self.max_col - self.min_col + 1

    @computed_field
    @property
    def ref(self) -> str:
        """The range as a spreadsheet writes it ("A3:P20")."""
        return (f"{get_column_letter(self.min_col)}{self.min_row}:"
                f"{get_column_letter(self.max_col)}{self.max_row}")


class TableColumn(_Frozen):
    """One column of a table, from its first to its last column (empty columns included)."""
    #: 1-based column index in the sheet
    index: int
    letter: str
    #: The header value of the column on each header row, top to bottom (a merged cell's value is
    #: repeated over every column it spans); empty when the table has no header row
    header: list[CellValue]
    #: The header values as one text, levels joined with " / "; None when every header cell is empty
    label: Optional[str]
    #: Type of the lowest non-empty header value; EMPTY when there is none
    header_type: CellType
    #: Dominant type of the data cells
    dtype: CellType
    non_empty_count: int


class RowLabel(_Frozen):
    """The text of the label column on one data row."""
    row: int
    label: str


class SequenceRun(_Frozen):
    """An ordered run of header values (two are enough in a header row) or of leading-column values."""
    orientation: SequenceOrientation
    #: The header row the run lies in (COLUMNS), or the column it runs down (ROWS)
    line: int
    #: First and last column (COLUMNS) or row (ROWS) of the run, inclusive
    first: int
    last: int
    kind: SequenceKind

    @computed_field
    @property
    def length(self) -> int:
        return self.last - self.first + 1


class DetectedTable(_Frozen):
    sheet: str
    source: TableSource
    #: The Excel table name, for a NATIVE table
    name: Optional[str] = None
    #: Header rows and data rows; the title is not part of it
    range: CellRange
    #: Title lines found above the table, joined with a line break
    title: Optional[str] = None
    title_refs: list[str] = []
    header_rows: list[int] = []
    columns: list[TableColumn]
    #: The column holding the row labels; None for a record list (each row is a record) and when
    #: the first column holds data
    label_column: Optional[int] = None
    row_labels: list[RowLabel] = []
    data_range: Optional[CellRange] = None
    data_row_count: int
    nature: TableNature
    sequences: list[SequenceRun] = []


class SheetNote(_Frozen):
    """A non-empty cell outside every table and title: a sheet title, a footnote, a stray value."""
    ref: str
    text: str


class SheetTables(_Frozen):
    name: str
    #: 0-based position in the workbook
    index: int
    kind: SheetKind
    hidden: bool
    #: Read without merged ranges, fonts and native tables (a read-only worksheet): titles in merged
    #: cells, bold headers over text-only columns and Excel table objects are not recognised as such
    read_only: bool = False
    tables: list[DetectedTable] = []
    #: The first ``DetectionOptions.max_notes`` notes, top to bottom then left to right
    notes: list[SheetNote] = []
    notes_total: int = 0


class WorkbookTables(_Frozen):
    sheets: list[SheetTables]
    #: The workbook was opened read-only (openpyxl could not open it in normal mode): see SheetTables.read_only
    read_only: bool = False

    @property
    def tables(self) -> list[DetectedTable]:
        """Every table of the workbook, sheet by sheet."""
        return [table for sheet in self.sheets for table in sheet.tables]


class DetectionOptions(_Frozen):
    """Thresholds of the detector. The defaults suit hand-made workbooks; none depends on content."""
    #: Empty columns tolerated inside a table (a gap between a label column and its values)
    max_column_gap: int = 3
    #: Empty rows tolerated inside a table (a gap between two sections)
    max_row_gap: int = 2
    max_header_rows: int = 5
    max_title_rows: int = 3
    #: Empty rows tolerated between a title block and the table under it
    max_title_gap: int = 1
    #: Share of a column's cells one type must hold to be its dtype (otherwise MIXED)
    dominant_share: float = 0.8
    #: Rows read below a candidate header row to learn the types it is compared with
    sample_rows: int = 200
    max_notes: int = 100
