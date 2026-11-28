"""
Structural predicates shared by the segmentation and the analysis of a table.

A header row is recognised by structure alone, never by what it says. One principle: a header cell is
the odd one out of its column. A row heads the rows under it when
- in the columns holding values (numbers, dates, booleans), its cells are of a type the body almost never
  holds there (a text over amounts; several dates over amounts: one date among amounts is a value), or
- at a table's top, over those columns, its values form an ordered run the body does not repeat
  (2024, 2025, 2026 over amounts), or, on the first row, in bold over plain rows (then two consecutive
  values are enough: 2026, 2027), or
- over text-only columns, it is bold where the body is not (first row), or it fills every column with
  distinct values none of which recurs below (first row, no formatting).
A header never repeats a label in two adjacent columns: a row of statuses ("late", "late", "ok") is data.

The header of a table is a contiguous run of header rows at its top, its very first row possibly an
atypical one (a row of codes over a row of names over a row of years); one definition, used everywhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from lys.core.utils.spreadsheet.grid import TYPED_KINDS, Box, Kind, SheetGrid
from lys.core.utils.spreadsheet.models import SequenceKind

#: A label holding one integer: its text before, the integer, its text after ("S1", "Week 12", "FY2026")
_NUMBERED = re.compile(r"^(\D*?)(\d+)(\D*)$")

#: Shortest run of values read as a sequence
MIN_SEQUENCE_LENGTH = 3

#: Share a type must hold among a column's cells to be called its type (segmentation shape checks)
HEADER_TYPE_SHARE = 0.6

#: Share of a column's body a type may hold and still be odd there: a header cell's type is rarer than this
RARE_SHARE = 0.1

#: Share of typed cells (numbers, dates, booleans) that makes a column a column of values
VALUE_COLUMN_SHARE = 0.5

#: Share of a region's width a row may fill and still be a sparse one (a title row); a lone cell always is
SPARSE_ROW_SHARE = 0.25

#: How many times denser than a sparse row the row it titles must be
DENSE_ROW_FACTOR = 2

#: Body rows read to tell whether an ordered header run is odd among them
SEQUENCE_SAMPLE_ROWS = 10


def dominant_kind(grid: SheetGrid, col: int, rows: list[int], share: float) -> tuple[Optional[Kind], int]:
    """
    The kind holding at least `share` of a column's non-empty, non-error cells over some rows.

    Returns:
        (kind or None when no kind reaches the share or the column is empty, number of counted cells)
    """
    return dominant_of(_kind_counts(grid, col, rows), share)


def dominant_of(counts: dict[Kind, int], share: float) -> tuple[Optional[Kind], int]:
    """
    The kind holding at least `share` of the non-error cells counted by kind (see ``dominant_kind``).

    Returns:
        (kind or None when no kind reaches the share or nothing but errors was counted, number of
        non-error cells)
    """
    counted = {kind: count for kind, count in counts.items() if kind is not Kind.ERROR}
    total = sum(counted.values())
    if not total:
        return None, 0
    kind, count = max(counted.items(), key=lambda item: item[1])
    return (kind if count >= share * total else None), total


def column_kind_counts(grid: SheetGrid, rows: list[int], min_col: int, max_col: int) -> dict[int, dict[Kind, int]]:
    """
    The cells of each kind (errors included) every column between two columns holds over some rows.

    Read cell by cell, so its cost is the number of values, never the area of the range: a sheet of one
    header row and one long column spans millions of cells and holds a few thousand.
    """
    counts: dict[int, dict[Kind, int]] = {}
    for row in rows:
        for col in grid.columns_in(row, min_col, max_col):
            kinds = counts.setdefault(col, {})
            kind = grid.kinds[(row, col)]
            kinds[kind] = kinds.get(kind, 0) + 1
    return counts


def _kind_counts(grid: SheetGrid, col: int, rows: list[int]) -> dict[Kind, int]:
    """The cells of each kind (errors included) one column holds over some rows."""
    counts: dict[Kind, int] = {}
    for row in rows:
        kind = grid.kinds.get((row, col))
        if kind is not None:
            counts[kind] = counts.get(kind, 0) + 1
    return counts


@dataclass
class _RunState:
    kind: SequenceKind
    last: Any
    step: Optional[int] = None
    prefix: str = ""
    suffix: str = ""


def _as_date(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return None


def _as_integer(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _numbered(value: Any) -> Optional[tuple[str, int, str]]:
    if not isinstance(value, str):
        return None
    match = _NUMBERED.match(value.strip())
    if match is None:
        return None
    return match.group(1).casefold(), int(match.group(2)), match.group(3).casefold()


def _start(value: Any) -> Optional[_RunState]:
    moment = _as_date(value)
    if moment is not None:
        return _RunState(SequenceKind.DATE, moment)
    integer = _as_integer(value)
    if integer is not None:
        return _RunState(SequenceKind.NUMBER, integer)
    numbered = _numbered(value)
    if numbered is not None:
        return _RunState(SequenceKind.NUMBERED_TEXT, numbered[1], prefix=numbered[0], suffix=numbered[2])
    return None


def _extends(state: _RunState, value: Any) -> bool:
    """Whether a value continues a run, updating the run when it does."""
    if state.kind is SequenceKind.DATE:
        moment = _as_date(value)
        if moment is None or moment <= state.last:
            return False
        state.last = moment
        return True
    if state.kind is SequenceKind.NUMBER:
        integer = _as_integer(value)
    else:
        numbered = _numbered(value)
        if numbered is None or (numbered[0], numbered[2]) != (state.prefix, state.suffix):
            return False
        integer = numbered[1]
    if integer is None:
        return False
    step = integer - state.last
    if step == 0 or (state.step is not None and step != state.step):
        return False
    state.step, state.last = step, integer
    return True


def sequence_runs(positions: list[tuple], min_length: int = MIN_SEQUENCE_LENGTH) -> list[tuple[int, int, SequenceKind]]:
    """
    The ordered runs in a line of values: strictly increasing dates, integers with a constant step,
    labels identical but for an integer with a constant step.

    Args:
        positions: (position, value) pairs, or (first, last, value) for a value spanning positions (a merged
            cell), in line order; a gap between two positions ends a run
        min_length: Shortest run returned. Two values make a constant step whatever they are, so a run of
            two counts only for dates or consecutive integers (2026, 2027); two numbered labels ("Option 1",
            "Option 2") are too weak a sign of an axis

    Returns:
        (first position, last position, kind) of each run of at least `min_length` values
    """
    spans = [item if len(item) == 3 else (item[0], item[0], item[1]) for item in positions]
    runs = []
    index = 0
    while index < len(spans):
        state = _start(spans[index][2])
        end = index
        if state is not None:
            while (end + 1 < len(spans) and spans[end + 1][0] == spans[end][1] + 1
                   and _extends(state, spans[end + 1][2])):
                end += 1
        length = end - index + 1
        consecutive = state is not None and (state.kind is SequenceKind.DATE or (
            state.kind is SequenceKind.NUMBER and abs(state.step or 0) == 1))
        if state is not None and length >= min_length and (length > 2 or consecutive):
            runs.append((spans[index][0], spans[end][1], state.kind))
            index = end + 1
        else:
            index += 1
    return runs


def row_spans(grid: SheetGrid, row: int, cols: list[int]) -> list[tuple[int, int, Any]]:
    """The values of a row over some columns, a merged cell counted once over the columns it spans."""
    spans = []
    for col in cols:
        merge = grid.merge_at(row, col)
        last = merge.max_col if merge is not None and merge.min_row == row else col
        spans.append((col, last, grid.value(row, col)))
    return spans


def _shares(grid: SheetGrid, col: int, rows: list[int]) -> tuple[dict[Kind, float], int]:
    counts = {kind: count for kind, count in _kind_counts(grid, col, rows).items() if kind is not Kind.ERROR}
    total = sum(counts.values())
    return ({kind: count / total for kind, count in counts.items()} if total else {}), total


def repeats_adjacent_label(grid: SheetGrid, row: int, cols: list[int]) -> bool:
    """Whether two cells side by side hold the same value: never column names, often category values."""
    for left, right in zip(cols, cols[1:]):
        if right != left + 1:
            continue
        first, second = grid.value(row, left), grid.value(row, right)
        if isinstance(first, str) and isinstance(second, str):
            first, second = first.strip().casefold(), second.strip().casefold()
        if first == second:
            return True
    return False


def is_header_row(
    grid: SheetGrid, row: int, min_col: int, max_col: int, body_rows: list[int], first: bool, axis: bool = False,
    formatting: bool = True, group_level: bool = False,
) -> bool:
    """
    Whether a row heads the rows under it (see the module docstring for the signals).

    Args:
        grid: The sheet's cells
        row: The candidate row
        min_col, max_col: The columns of the table
        body_rows: Rows under the candidate, a sample of the table's body
        first: Whether the candidate is the table's first row (enables the text-only fallback)
        axis: Whether an ordered run of values may decide (a table's top: its first row, a row under a header
            row or under a merged group label; elsewhere a row of figures could give one)
        formatting: Whether bold may decide (a table's first row; deeper down a bold row is a total)
        group_level: Whether the row sits over another header row, as a level of groups: it may then repeat
            a label over adjacent columns (a group written in each of its columns)
    """
    cols = grid.columns_in(row, min_col, max_col)
    if not cols or not body_rows or (len(cols) < 2 and max_col > min_col):
        return False
    if not group_level and repeats_adjacent_label(grid, row, cols):
        return False
    shares = {col: _shares(grid, col, body_rows)[0] for col in cols}
    values = [col for col in cols if sum(shares[col].get(kind, 0.0) for kind in TYPED_KINDS) >= VALUE_COLUMN_SHARE]
    if values:
        odd = [col for col in values if shares[col].get(grid.kind(row, col), 0.0) <= RARE_SHARE
               and grid.kind(row, col) is not Kind.ERROR]
        texts = sum(1 for col in odd if grid.kind(row, col) is Kind.TEXT)
        others = len(odd) - texts
        breaks = texts + (others if others >= 2 else 0)
        if breaks and 2 * breaks >= len(values):
            return True
        if not axis:
            return False
        # On a table's first row, bold over plain rows is a second, independent signal: it lets a run of two
        # values count (actual 2026, budget 2027) and an ordered body (rows of linear projections) pass
        bold = formatting and _bold_over_plain(grid, row, cols, body_rows[0], min_col, max_col)
        runs = sequence_runs(row_spans(grid, row, values), min_length=2 if bold else MIN_SEQUENCE_LENGTH)
        covered = sorted({col for start, last, _ in runs for col in values if start <= col <= last})
        if 2 * len(covered) < len(values):
            return False
        if bold:
            return True
        # Odd one out again: an ordered run heads the body when the body's rows are not ordered alike
        sample = body_rows[:SEQUENCE_SAMPLE_ROWS]
        ordered = sum(1 for body_row in sample if sequence_runs(row_spans(grid, body_row, covered)))
        return 2 * ordered < len(sample)
    if formatting and _bold_over_plain(grid, row, cols, body_rows[0], min_col, max_col):
        return True
    return first and _distinct_text_header(grid, row, cols, min_col, max_col, body_rows)


def _bold_over_plain(grid: SheetGrid, row: int, cols: list[int], next_row: int, min_col: int, max_col: int) -> bool:
    """Whether a row is bold throughout over a row that is not."""
    next_cols = grid.columns_in(next_row, min_col, max_col)
    return (all(grid.is_bold(row, col) for col in cols) and bool(next_cols)
            and not all(grid.is_bold(next_row, col) for col in next_cols))


def is_group_label(grid: SheetGrid, row: int, box: Box) -> bool:
    """A row holding a single merged cell spanning several columns: a label over a group of columns."""
    cols = grid.columns_in(row, box.min_col, box.max_col)
    merge = grid.merge_at(row, cols[0]) if len(cols) == 1 else None
    return merge is not None and merge.width > 1


def header_count(grid: SheetGrid, rows: list[int], box: Box, max_header_rows: int, sample_rows: int) -> int:
    """
    How many of the top rows (titles already removed) head the table: a contiguous run of header rows from
    the top, at most ``max_header_rows``. The very first row may be an atypical one (a row of codes or units)
    when the row right under it is a header row; below it, a row that is no header ends the header. A row
    repeating a label over adjacent columns heads the table only as a level of groups over a header row
    naming its columns.
    """
    limit = min(max_header_rows, len(rows) - 1)
    flags: list[bool] = []
    groups: list[bool] = []
    for index in range(limit):
        row = rows[index]
        body = rows[index + 1:index + 1 + sample_rows]
        axis = index <= 1 or flags[-1] or is_group_label(grid, rows[index - 1], box)
        named = is_header_row(grid, row, box.min_col, box.max_col, body, first=index == 0, axis=axis,
                              formatting=index == 0)
        grouped = not named and is_header_row(grid, row, box.min_col, box.max_col, body, first=index == 0,
                                              axis=axis, formatting=index == 0, group_level=True)
        flags.append(named or grouped)
        groups.append(grouped)
        if index >= 1 and not flags[-1]:
            break
    # A level of groups needs a header naming the columns right under it
    for index in range(len(flags)):
        if groups[index] and not (index + 1 < len(flags) and flags[index + 1] and not groups[index + 1]):
            flags[index] = False
    start = 0 if flags and flags[0] else 1
    count = start
    for flag in flags[start:]:
        if not flag:
            break
        count += 1
    return count if count > start else 0


def sparse_row_count(box: Box) -> int:
    """The most cells a row of a region may hold and still be a sparse one (SPARSE_ROW_SHARE of its width)."""
    return max(1, int(box.width * SPARSE_ROW_SHARE))


def title_rows(grid: SheetGrid, rows: list[int], box: Box, limit: int) -> list[int]:
    """
    The title rows on top of a region: sparse rows (a lone cell, or at most a quarter of the region's width)
    followed, within `limit` rows, by a row at least twice as dense. Never a row carrying an ordered run
    (an axis) nor a merged cell spanning some value columns only (a group label over them).
    """
    counts = [grid.count_in(row, box.min_col, box.max_col) for row in rows]
    sparse = sparse_row_count(box)
    titles: list[int] = []
    for index, row in enumerate(rows[:limit]):
        cols = grid.columns_in(row, box.min_col, box.max_col)
        if len(cols) > sparse or sequence_runs(row_spans(grid, row, cols)):
            break
        merge = grid.merge_at(row, cols[0])
        if len(cols) == 1 and merge is not None and merge.min_col > box.min_col and merge.width > 1:
            break
        dense = next((position for position in range(index + 1, len(rows))
                      if counts[position] >= max(2, DENSE_ROW_FACTOR * len(cols))), None)
        if dense is None or dense > limit:
            break
        titles.append(row)
    return titles


def _distinct_text_header(
    grid: SheetGrid, row: int, cols: list[int], min_col: int, max_col: int, body_rows: list[int],
) -> bool:
    """A first row of a text-only table: every used column filled, its values distinct and absent below."""
    used = {col for body_row in body_rows for col in grid.columns_in(body_row, min_col, max_col)}
    if len(cols) < 2 or not used.issubset(cols):
        return False
    labels = [str(grid.value(row, col)).strip().casefold() for col in cols]
    if len(set(labels)) != len(labels):
        return False
    for col, label in zip(cols, labels):
        for body_row in body_rows:
            value = grid.value(body_row, col)
            if isinstance(value, str) and value.strip().casefold() == label:
                return False
    return True
