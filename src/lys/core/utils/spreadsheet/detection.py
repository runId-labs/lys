"""
Public entry points: a workbook (bytes, path or stream), an open workbook, or one sheet -> its tables.
"""
from __future__ import annotations

from pathlib import Path
from typing import IO, Any, Iterable, Optional, Union

from openpyxl.chartsheet import Chartsheet
from openpyxl.utils import range_boundaries

from lys.core.utils.spreadsheet.analysis import TableDraft, analyze_native, analyze_region
from lys.core.utils.spreadsheet.grid import Box, SheetGrid, text_of
from lys.core.utils.spreadsheet.models import (
    DetectionOptions,
    SheetKind,
    SheetNote,
    SheetTables,
    WorkbookTables,
)
from lys.core.utils.spreadsheet.loading import open_workbook
from lys.core.utils.spreadsheet.segmentation import find_regions, is_lone_box

WorkbookSource = Union[bytes, bytearray, str, Path, IO[bytes]]


def detect_tables(
    source: WorkbookSource,
    *,
    sheet_names: Optional[Iterable[str]] = None,
    options: Optional[DetectionOptions] = None,
) -> WorkbookTables:
    """
    Open an .xlsx / .xlsm workbook and describe the tables of its sheets.

    The workbook is opened with the values the spreadsheet saved (``data_only``: formulas are not
    evaluated, macros never run), in normal mode, which merged ranges, fonts and native tables need.
    When openpyxl cannot open it that way, see ``loading`` for the fallbacks; a read-only fallback is
    reported by ``WorkbookTables.read_only``.

    Args:
        source: The file content, its path, or a binary stream
        sheet_names: Only these sheets (all when None)
        options: Detection thresholds (defaults when None)

    Raises:
        What openpyxl raises on a file it cannot open in any mode (``zipfile.BadZipFile``,
        ``InvalidFileException``...). Size limits are the caller's: this function trusts its input.
    """
    workbook = open_workbook(_content_of(source))
    try:
        return detect_workbook_tables(workbook, sheet_names=sheet_names, options=options)
    finally:
        workbook.close()


def _content_of(source: WorkbookSource) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    return source.read()


def detect_workbook_tables(
    workbook: Any,
    *,
    sheet_names: Optional[Iterable[str]] = None,
    options: Optional[DetectionOptions] = None,
) -> WorkbookTables:
    """Describe the tables of an open openpyxl workbook, sheet by sheet in workbook order."""
    wanted = set(sheet_names) if sheet_names is not None else None
    sheets = [
        detect_sheet_tables(workbook[name], index=index, options=options)
        for index, name in enumerate(workbook.sheetnames)
        if wanted is None or name in wanted
    ]
    return WorkbookTables(sheets=sheets, read_only=bool(getattr(workbook, "read_only", False)))


def detect_sheet_tables(sheet: Any, *, index: Optional[int] = None,
                        options: Optional[DetectionOptions] = None) -> SheetTables:
    """
    Describe the tables of one sheet.

    A chart sheet has no cells: it is returned with no table. A read-only worksheet is read without its
    merged ranges, fonts and native tables (openpyxl does not load them in that mode).
    """
    options = options or DetectionOptions()
    if index is None:
        index = sheet.parent.sheetnames.index(sheet.title)
    hidden = getattr(sheet, "sheet_state", "visible") != "visible"
    if isinstance(sheet, Chartsheet) or not hasattr(sheet, "iter_rows"):
        return SheetTables(name=sheet.title, index=index, kind=SheetKind.CHARTSHEET, hidden=hidden)

    grid = SheetGrid.from_worksheet(sheet)
    drafts: list[TableDraft] = []
    native_boxes = []
    for table in getattr(sheet, "tables", {}).values():
        min_col, min_row, max_col, max_row = range_boundaries(table.ref)
        box = Box(min_row, min_col, max_row, max_col)
        native_boxes.append(box)
        header_count = 1 if table.headerRowCount is None else int(table.headerRowCount)
        drafts.append(analyze_native(grid, box, header_count, table.displayName, options))

    loose: list[Box] = []
    for box in find_regions(grid, native_boxes, options):
        draft = None if is_lone_box(grid, box) and box.width == 1 and box.height <= options.max_title_rows \
            else analyze_region(grid, box, options)
        if draft is None:
            loose.append(box)
        else:
            drafts.append(draft)
    _attach_titles(grid, drafts, loose, options)
    drafts.sort(key=lambda draft: (draft.box.min_row, draft.box.min_col))

    tables = [draft.to_model(grid, sheet.title) for draft in drafts]
    notes, notes_total = _notes(grid, drafts, options.max_notes)
    return SheetTables(
        name=sheet.title, index=index, kind=SheetKind.WORKSHEET, hidden=hidden, read_only=grid.read_only,
        tables=tables, notes=notes, notes_total=notes_total,
    )


def _attach_titles(grid: SheetGrid, drafts: list[TableDraft], loose: list[Box], options: DetectionOptions) -> None:
    """Give an untitled table the block of lone cells just above it (a gap of a few empty rows allowed)."""
    used: set[int] = set()
    for draft in sorted(drafts, key=lambda item: (item.box.min_row, item.box.min_col)):
        if draft.title_cells:
            continue
        for position, block in enumerate(loose):
            if position in used or not is_lone_box(grid, block):
                continue
            gap = draft.box.min_row - block.max_row - 1
            if not 0 <= gap <= options.max_title_gap:
                continue
            if not draft.box.min_col <= block.min_col <= draft.box.max_col:
                continue
            rows = grid.content_rows(block)
            if len(rows) > options.max_title_rows:
                continue
            draft.title_cells = [(row, col) for row in rows
                                 for col in grid.columns_in(row, block.min_col, block.max_col)]
            used.add(position)
            break


def _notes(grid: SheetGrid, drafts: list[TableDraft], limit: int) -> tuple[list[SheetNote], int]:
    """The first ``limit`` values of a sheet outside its tables and their titles, and how many there are."""
    covered = {cell for draft in drafts for cell in draft.title_cells}
    spans: dict[int, list[tuple[int, int]]] = {}
    for draft in drafts:
        for row in range(draft.box.min_row, draft.box.max_row + 1):
            spans.setdefault(row, []).append((draft.box.min_col, draft.box.max_col))
    notes: list[SheetNote] = []
    total = 0
    for row, col in sorted(grid.values):
        if (row, col) in covered or any(first <= col <= last for first, last in spans.get(row, ())):
            continue
        total += 1
        if len(notes) < limit:
            notes.append(SheetNote(ref=grid.ref(row, col), text=text_of(grid.value(row, col))))
    return notes, total
