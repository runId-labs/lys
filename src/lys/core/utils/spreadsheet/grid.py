"""
A worksheet's non-empty cells, typed, with the merged ranges and the boxes the detector works on.

Only the cells the file stores are read: a normal-mode worksheet keeps them in ``_cells`` (iterating
``iter_rows`` up to ``max_row`` would create every missing cell, and a single formatted cell far down a
sheet would make that millions). A read-only worksheet is streamed instead; it carries no merged ranges
and no fonts, so the signals that rely on them are not available there.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Optional

from openpyxl.utils import get_column_letter

from lys.core.utils.spreadsheet.models import CellRange, CellType


class Kind(Enum):
    """Type of one non-empty cell."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOL = "bool"
    #: An Excel error value ("#DIV/0!"): a computed cell, typed like its column, so ignored in type counts
    ERROR = "error"


#: Kinds a header cell is told apart from: a text header over numbers, dates or booleans
TYPED_KINDS = frozenset({Kind.NUMBER, Kind.DATE, Kind.BOOL})

KIND_TO_CELL_TYPE = {
    Kind.TEXT: CellType.TEXT,
    Kind.NUMBER: CellType.NUMBER,
    Kind.DATE: CellType.DATE,
    Kind.BOOL: CellType.BOOL,
}

EXCEL_ERRORS = frozenset({
    "#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A", "#GETTING_DATA", "#SPILL!", "#CALC!",
})


def kind_of(value: Any) -> Optional[Kind]:
    """The kind of a cell value; None for an empty cell (None, or a string of blanks)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return Kind.BOOL
    if isinstance(value, (int, float, Decimal, timedelta)):
        return Kind.NUMBER
    if isinstance(value, (datetime, date, time)):
        return Kind.DATE
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return Kind.ERROR if stripped in EXCEL_ERRORS else Kind.TEXT
    return Kind.TEXT


def text_of(value: Any) -> str:
    """A cell value as a short text: dates in ISO form, whole floats without their decimal part."""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == time() else value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def output_value(value: Any) -> Any:
    """A header value in a type the output models carry."""
    if value is None or isinstance(value, (bool, int, float, datetime, date, time, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    return text_of(value)


@dataclass
class Box:
    """A mutable rectangle of cells (1-based, inclusive), the unit the segmentation merges."""
    min_row: int
    min_col: int
    max_row: int
    max_col: int

    @property
    def width(self) -> int:
        return self.max_col - self.min_col + 1

    @property
    def height(self) -> int:
        return self.max_row - self.min_row + 1

    def absorb(self, other: "Box") -> None:
        self.min_row = min(self.min_row, other.min_row)
        self.min_col = min(self.min_col, other.min_col)
        self.max_row = max(self.max_row, other.max_row)
        self.max_col = max(self.max_col, other.max_col)

    def intersects(self, other: "Box") -> bool:
        return (self.min_row <= other.max_row and other.min_row <= self.max_row
                and self.min_col <= other.max_col and other.min_col <= self.max_col)

    def contains(self, row: int, col: int) -> bool:
        return self.min_row <= row <= self.max_row and self.min_col <= col <= self.max_col

    def to_range(self) -> CellRange:
        return CellRange(min_row=self.min_row, min_col=self.min_col, max_row=self.max_row, max_col=self.max_col)


class SheetGrid:
    """The non-empty cells of one worksheet, by row, with their kinds and merged ranges."""

    def __init__(self, values: dict[tuple[int, int], Any], merges: Iterable[Box], worksheet: Any = None):
        self.values: dict[tuple[int, int], Any] = {}
        self.kinds: dict[tuple[int, int], Kind] = {}
        columns_by_row: dict[int, list[int]] = {}
        for (row, col), value in values.items():
            kind = kind_of(value)
            if kind is None:
                continue
            self.values[(row, col)] = value
            self.kinds[(row, col)] = kind
            columns_by_row.setdefault(row, []).append(col)
        self.columns_by_row = {row: sorted(cols) for row, cols in columns_by_row.items()}
        # A merged range holds its value in its top-left cell only; one with an empty anchor is formatting
        self.merges = [merge for merge in merges if (merge.min_row, merge.min_col) in self.values]
        self._merge_of: dict[tuple[int, int], Box] = {}
        for merge in self.merges:
            for row in range(merge.min_row, merge.max_row + 1):
                for col in range(merge.min_col, merge.max_col + 1):
                    self._merge_of[(row, col)] = merge
        self._worksheet = worksheet

    @classmethod
    def from_worksheet(cls, worksheet: Any) -> "SheetGrid":
        stored = getattr(worksheet, "_cells", None)
        if isinstance(stored, dict):
            values = {key: cell.value for key, cell in stored.items() if cell.value is not None}
            merges = [Box(rng.min_row, rng.min_col, rng.max_row, rng.max_col)
                      for rng in worksheet.merged_cells.ranges]
            return cls(values, merges, worksheet)
        values = {}
        for row in worksheet.iter_rows():
            for cell in row:
                value = getattr(cell, "value", None)
                if value is not None:
                    values[(cell.row, cell.column)] = value
        return cls(values, [])

    @property
    def read_only(self) -> bool:
        """Whether the sheet was read without merged ranges and fonts (a read-only worksheet)."""
        return self._worksheet is None

    def value(self, row: int, col: int) -> Any:
        return self.values.get((row, col))

    def kind(self, row: int, col: int) -> Optional[Kind]:
        return self.kinds.get((row, col))

    def shown_value(self, row: int, col: int) -> Any:
        """The value a reader sees in a cell: a merged range shows its anchor's value in every cell."""
        merge = self._merge_of.get((row, col))
        if merge is not None:
            return self.values.get((merge.min_row, merge.min_col))
        return self.values.get((row, col))

    def merge_at(self, row: int, col: int) -> Optional[Box]:
        return self._merge_of.get((row, col))

    def columns_in(self, row: int, min_col: int, max_col: int) -> list[int]:
        """The non-empty columns of a row between min_col and max_col."""
        cols = self.columns_by_row.get(row)
        if not cols:
            return []
        return cols[bisect.bisect_left(cols, min_col):bisect.bisect_right(cols, max_col)]

    def count_in(self, row: int, min_col: int, max_col: int) -> int:
        cols = self.columns_by_row.get(row)
        if not cols:
            return 0
        return bisect.bisect_right(cols, max_col) - bisect.bisect_left(cols, min_col)

    def content_rows(self, box: Box, limit: Optional[int] = None) -> list[int]:
        """
        The rows of a box holding at least one value within its columns, top to bottom: all of them, or
        the first ``limit`` (what a caller reading only the top of a box asks, whatever the box's height).
        """
        rows: list[int] = []
        for row in range(box.min_row, box.max_row + 1):
            if limit is not None and len(rows) >= limit:
                break
            if self.count_in(row, box.min_col, box.max_col):
                rows.append(row)
        return rows

    def last_content_rows(self, box: Box, limit: int) -> list[int]:
        """The last ``limit`` rows of a box holding a value within its columns, top to bottom."""
        rows: list[int] = []
        for row in range(box.max_row, box.min_row - 1, -1):
            if len(rows) >= limit:
                break
            if self.count_in(row, box.min_col, box.max_col):
                rows.append(row)
        rows.reverse()
        return rows

    def row_extent(self, row: int, min_col: int, max_col: int) -> Optional[Box]:
        """The smallest box holding the values of one row between two columns, and their merged ranges."""
        cols = self.columns_in(row, min_col, max_col)
        if not cols:
            return None
        first, last = cols[0], cols[-1]
        for col in (first, last):
            merge = self._merge_of.get((row, col))
            if merge is not None:
                first, last = min(first, max(merge.min_col, min_col)), max(last, min(merge.max_col, max_col))
        return Box(row, first, row, last)

    def shrink(self, rows: list[int], min_col: int, max_col: int) -> Optional[Box]:
        """The smallest box holding the values of these rows between two columns, and their merged ranges."""
        box: Optional[Box] = None
        for row in rows:
            part = self.row_extent(row, min_col, max_col)
            if part is None:
                continue
            if box is None:
                box = part
            else:
                box.absorb(part)
        return box

    def is_bold(self, row: int, col: int) -> bool:
        """Whether a non-empty cell is bold; always False for a read-only worksheet (no fonts)."""
        if self._worksheet is None or (row, col) not in self.values:
            return False
        font = self._worksheet.cell(row=row, column=col).font
        return bool(font is not None and font.b)

    @staticmethod
    def ref(row: int, col: int) -> str:
        return f"{get_column_letter(col)}{row}"
