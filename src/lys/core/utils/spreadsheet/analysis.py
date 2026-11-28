"""
Describing one region: its title, header rows, columns, label column, sequences and nature.

The nature is read from the structure the detection found, after it; it never decides whether a table
or a header exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from openpyxl.utils import get_column_letter

from lys.core.utils.spreadsheet.grid import KIND_TO_CELL_TYPE, Box, Kind, SheetGrid, kind_of, output_value, text_of
from lys.core.utils.spreadsheet.models import (
    CellType,
    DetectedTable,
    DetectionOptions,
    RowLabel,
    SequenceKind,
    SequenceOrientation,
    SequenceRun,
    TableColumn,
    TableNature,
    TableSource,
)
from lys.core.utils.spreadsheet.rules import (
    column_kind_counts,
    dominant_of,
    header_count,
    row_spans,
    sequence_runs,
    title_rows,
)

#: Value columns a key/value block may hold, a single one of them typed (comments, units aside)
MAX_KEY_VALUE_COLUMNS = 3


@dataclass
class TableDraft:
    """A table being described; the title can still be attached from a block above it."""
    box: Box
    source: TableSource
    name: Optional[str]
    header_rows: list[int]
    columns: list[TableColumn]
    label_column: Optional[int]
    row_labels: list[RowLabel]
    data_box: Optional[Box]
    data_row_count: int
    nature: TableNature
    sequences: list[SequenceRun]
    title_cells: list[tuple[int, int]] = field(default_factory=list)

    def to_model(self, grid: SheetGrid, sheet: str) -> DetectedTable:
        lines: dict[int, list[str]] = {}
        for row, col in self.title_cells:
            lines.setdefault(row, []).append(text_of(grid.value(row, col)))
        title = "\n".join(" ".join(texts) for _, texts in sorted(lines.items())) or None
        return DetectedTable(
            sheet=sheet,
            source=self.source,
            name=self.name,
            range=self.box.to_range(),
            title=title,
            title_refs=[grid.ref(row, col) for row, col in self.title_cells],
            header_rows=self.header_rows,
            columns=self.columns,
            label_column=self.label_column,
            row_labels=self.row_labels,
            data_range=self.data_box.to_range() if self.data_box is not None else None,
            data_row_count=self.data_row_count,
            nature=self.nature,
            sequences=self.sequences,
        )


def analyze_region(grid: SheetGrid, box: Box, options: DetectionOptions) -> Optional[TableDraft]:
    """
    Describe a region found by the segmentation.

    Returns:
        The table, or None when the region is too small to be one (its cells are then sheet notes)
    """
    rows = grid.content_rows(box)
    titles = title_rows(grid, rows, box, options.max_title_rows)
    rows = rows[len(titles):]
    if not rows:
        return None
    table_box = grid.shrink(rows, box.min_col, box.max_col)
    used = {col for row in rows for col in grid.columns_in(row, table_box.min_col, table_box.max_col)}
    if len(rows) < 2 or (len(used) < 2 and len(rows) < 3):
        return None
    header_rows = rows[:header_count(grid, rows, table_box, options.max_header_rows, options.sample_rows)]
    if len(used) < 2 and not header_rows:
        # A single column without a header: a column of notes, not a table
        return None
    draft = _describe(grid, table_box, header_rows, rows[len(header_rows):], options, TableSource.REGION, None)
    draft.title_cells = [(row, col) for row in titles for col in grid.columns_in(row, box.min_col, box.max_col)]
    return draft


def analyze_native(grid: SheetGrid, box: Box, header_rows: int, name: str, options: DetectionOptions) -> TableDraft:
    """Describe an Excel table object: its range and header row count are the file's."""
    headers = list(range(box.min_row, min(box.min_row + header_rows, box.max_row + 1)))
    body_rows = [row for row in grid.content_rows(box) if row >= box.min_row + header_rows]
    return _describe(grid, box, headers, body_rows, options, TableSource.NATIVE, name)


def _describe(
    grid: SheetGrid,
    box: Box,
    header_rows: list[int],
    body_rows: list[int],
    options: DetectionOptions,
    source: TableSource,
    name: Optional[str],
) -> TableDraft:
    # Counted cell by cell: a column is never read down the table's height when it holds nothing there
    counts = column_kind_counts(grid, body_rows, box.min_col, box.max_col)
    columns = [
        _column(grid, col, header_rows, counts.get(col, {}), options) for col in range(box.min_col, box.max_col + 1)
    ]
    used = [column for column in columns if column.non_empty_count]

    label_column = None
    if used and used[0].dtype is CellType.TEXT and (
            len(used) == 2 or any(column.dtype is not CellType.TEXT for column in used[1:])):
        label_column = used[0].index

    sequences = _header_sequences(grid, columns, header_rows, label_column)
    value_columns = [column for column in used if column.index != label_column]
    covered = {col for run in sequences for col in range(run.first, run.last + 1)}
    in_sequence = sum(1 for column in value_columns if column.index in covered)

    if value_columns and 2 * in_sequence >= len(value_columns):
        nature = TableNature.TIME_SERIES
    else:
        sequences = []
        row_run = _row_sequence(grid, used, body_rows)
        typed_values = sum(1 for column in value_columns if column.dtype is not CellType.TEXT)
        if row_run is not None:
            nature, sequences, label_column = TableNature.TIME_SERIES, [row_run], None
        elif label_column is not None and 1 <= len(value_columns) <= MAX_KEY_VALUE_COLUMNS and typed_values <= 1:
            nature = TableNature.KEY_VALUE
        elif header_rows:
            nature, label_column = TableNature.RECORD_LIST, None
        else:
            nature = TableNature.OTHER

    row_labels = []
    if label_column is not None:
        for row in body_rows:
            value = grid.value(row, label_column)
            if value is not None:
                row_labels.append(RowLabel(row=row, label=text_of(value)))

    return TableDraft(
        box=box,
        source=source,
        name=name,
        header_rows=header_rows,
        columns=columns,
        label_column=label_column,
        row_labels=row_labels,
        data_box=grid.shrink(body_rows, box.min_col, box.max_col) if body_rows else None,
        data_row_count=len(body_rows),
        nature=nature,
        sequences=sequences,
    )


def _cell_type(kind: Optional[Kind]) -> CellType:
    if kind is None:
        return CellType.EMPTY
    return KIND_TO_CELL_TYPE.get(kind, CellType.TEXT)


def _column(grid: SheetGrid, col: int, header_rows: list[int], body_kinds: dict[Kind, int],
            options: DetectionOptions) -> TableColumn:
    """One column of a table, from its header cells and the cells of each kind its body holds."""
    header = [output_value(grid.shown_value(row, col)) for row in header_rows]
    texts: list[str] = []
    header_kind = None
    for value in header:
        kind = kind_of(value)
        if kind is None:
            continue
        header_kind = kind
        text = text_of(value)
        if not texts or texts[-1] != text:
            texts.append(text)
    kind, counted = dominant_of(body_kinds, options.dominant_share)
    non_empty = sum(body_kinds.values())
    if not non_empty:
        dtype = CellType.EMPTY
    elif not counted:
        # Only error values: the column computes something that failed
        dtype = CellType.MIXED
    else:
        dtype = _cell_type(kind) if kind is not None else CellType.MIXED
    return TableColumn(
        index=col,
        letter=get_column_letter(col),
        header=header,
        label=" / ".join(texts) or None,
        header_type=_cell_type(header_kind),
        dtype=dtype,
        non_empty_count=non_empty,
    )


def _header_sequences(grid: SheetGrid, columns: list[TableColumn], header_rows: list[int],
                      label_column: Optional[int]) -> list[SequenceRun]:
    runs = []
    for row in header_rows:
        cols = [column.index for column in columns
                if column.index != label_column and kind_of(grid.value(row, column.index)) is not None]
        runs.extend(
            SequenceRun(orientation=SequenceOrientation.COLUMNS, line=row, first=first, last=last, kind=kind)
            # The rows are known to be header rows: two consecutive values already make an axis there
            for first, last, kind in sequence_runs(row_spans(grid, row, cols), min_length=2)
        )
    return runs


def _row_sequence(grid: SheetGrid, used: list[TableColumn], body_rows: list[int]) -> Optional[SequenceRun]:
    """A leading date column, increasing down most of the rows, beside numeric columns."""
    if len(used) < 2 or used[0].dtype is not CellType.DATE:
        return None
    others = used[1:]
    if 2 * sum(1 for column in others if column.dtype is CellType.NUMBER) < len(others):
        return None
    col = used[0].index
    dated = [row for row in body_rows if grid.kind(row, col) is Kind.DATE]
    runs = sequence_runs([(index, grid.value(row, col)) for index, row in enumerate(dated)])
    best = max(runs, key=lambda run: run[1] - run[0], default=None)
    if best is None or best[2] is not SequenceKind.DATE or 2 * (best[1] - best[0] + 1) < len(dated):
        return None
    return SequenceRun(orientation=SequenceOrientation.ROWS, line=col, first=dated[best[0]],
                       last=dated[best[1]], kind=SequenceKind.DATE)
