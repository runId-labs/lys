"""
Cutting a worksheet into regions, each a candidate table.

1. Connected components of non-empty cells (4-connectivity; a merged range counts as filled), found row
   by row on runs of consecutive columns.
2. Side by side, a component joins the one on its left (at most ``max_column_gap`` empty columns apart,
   sharing most of their rows) unless it has its own row keys: it starts with a column of keys (text or
   dates) followed by values, or holds a column of the kind of the left block's key column followed by
   values. An empty column between row labels and their values does not cut a table; two tables each with
   its labels (or its dates) stay apart. Farther apart, a block of text alone joins the values on its right
   when it labels them row for row (same rows, the values' header rows aside) with nothing in between.
3. Stacked, a component joins the one above (at most ``max_row_gap`` empty rows apart) when the upper one
   is its header, or when it opens on no header of its own and its body has the shape of the upper's
   (text where it holds text, values where it holds values), a titled block joining only a table whose
   header its sections can share. A blank line between sections does not cut a table; a summary and the
   list under it, or two titled blocks, stay apart.
4. Inside a region, a new table starts at a header row that follows data rows: under a title row, or
   repeating the region's top header (same types, column by column).

Whether a block opens on a header is answered by one definition (``rules.header_count``) everywhere.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from lys.core.utils.spreadsheet.grid import TYPED_KINDS, Box, Kind, SheetGrid
from lys.core.utils.spreadsheet.models import DetectionOptions
from lys.core.utils.spreadsheet.rules import (
    DENSE_ROW_FACTOR,
    HEADER_TYPE_SHARE,
    column_kind_counts,
    dominant_kind,
    dominant_of,
    header_count,
    is_header_row,
    sparse_row_count,
    title_rows,
)

#: Share of the taller of two side-by-side components their common rows must cover to be joined
SIDE_BY_SIDE_ROW_SHARE = 0.6

#: Share of the narrower of two stacked components their common columns must cover to be joined
STACKED_COLUMN_SHARE = 0.5


def find_regions(grid: SheetGrid, masked: list[Box], options: DetectionOptions) -> list[Box]:
    """
    The regions of a sheet outside the masked boxes (its native tables), top to bottom, left to right.
    """
    boxes = _components(grid, masked)
    # Side-by-side and stacked joins feed each other (a label column cut by a blank row joins its values
    # once its pieces are stacked): both run until nothing changes
    count = None
    while count != len(boxes):
        count = len(boxes)
        boxes = _merge_overlapping(_bridge_columns(grid, boxes, options))
        boxes = _merge_overlapping(_bridge_label_blocks(grid, boxes, options))
        boxes = _merge_overlapping(_bridge_rows(grid, boxes, options))
    regions = [part for box in boxes for part in _split_at_inner_headers(grid, box, options)]
    return sorted(regions, key=lambda box: (box.min_row, box.min_col))


def is_lone_box(grid: SheetGrid, box: Box) -> bool:
    """Whether every row of a box holds a single value: a title block or a column of notes."""
    return all(grid.count_in(row, box.min_col, box.max_col) <= 1 for row in range(box.min_row, box.max_row + 1))


def _components(grid: SheetGrid, masked: list[Box]) -> list[Box]:
    occupied: dict[int, set[int]] = defaultdict(set)
    for row, col in grid.values:
        if not any(box.contains(row, col) for box in masked):
            occupied[row].add(col)
    for merge in grid.merges:
        if any(box.contains(merge.min_row, merge.min_col) for box in masked):
            continue
        for row in range(merge.min_row, merge.max_row + 1):
            occupied[row].update(range(merge.min_col, merge.max_col + 1))

    parent: list[int] = []
    run_boxes: list[Box] = []

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    previous_row, previous_runs = None, []
    for row in sorted(occupied):
        runs = []
        start = last = None
        for col in sorted(occupied[row]):
            if start is not None and col == last + 1:
                last = col
                continue
            if start is not None:
                runs.append((start, last))
            start = last = col
        runs.append((start, last))

        current = []
        above = previous_runs if previous_row == row - 1 else []
        pointer = 0
        for start, last in runs:
            index = len(parent)
            parent.append(index)
            run_boxes.append(Box(row, start, row, last))
            current.append((start, last, index))
            while pointer < len(above) and above[pointer][1] < start:
                pointer += 1
            probe = pointer
            while probe < len(above) and above[probe][0] <= last:
                root_a, root_b = find(above[probe][2]), find(index)
                if root_a != root_b:
                    parent[root_b] = root_a
                probe += 1
        previous_row, previous_runs = row, current

    by_root: dict[int, Box] = {}
    for index, box in enumerate(run_boxes):
        root = find(index)
        if root in by_root:
            by_root[root].absorb(box)
        else:
            by_root[root] = Box(box.min_row, box.min_col, box.max_row, box.max_col)
    return list(by_root.values())


def _column_kinds(grid: SheetGrid, box: Box, options: DetectionOptions) -> list[Optional[Kind]]:
    """The type of each column of a box, read below its first row."""
    rows = grid.content_rows(box, limit=options.sample_rows + 1)[1:] or [box.min_row]
    counts = column_kind_counts(grid, rows, box.min_col, box.max_col)
    return [dominant_of(counts.get(col, {}), HEADER_TYPE_SHARE)[0] for col in range(box.min_col, box.max_col + 1)]


def _has_own_keys(grid: SheetGrid, left: Box, right: Box, options: DetectionOptions) -> bool:
    """
    Whether the right box carries its own row keys: it starts with a column of keys (text or dates) followed
    by values, or holds a column of the kind of the left box's key column (its first) followed by another
    kind (codes, then labels, then values). A box of text alone beside a text key column (a list beside a
    list) stands on its own too; a single column (comments beside a table) never does.
    """
    if right.width == 1:
        return False
    key = _column_kinds(grid, Box(left.min_row, left.min_col, left.max_row, left.min_col), options)[0]
    kinds = [kind for kind in _column_kinds(grid, right, options) if kind is not None]
    if not kinds or key is None:
        return False
    if kinds[0] in (Kind.TEXT, Kind.DATE) and any(kind is not kinds[0] for kind in kinds[1:]):
        return True
    for position, kind in enumerate(kinds):
        if kind is key and any(other is not key for other in kinds[position + 1:]):
            return True
    return key is Kind.TEXT and all(kind is Kind.TEXT for kind in kinds)


def _bridge_columns(grid: SheetGrid, boxes: list[Box], options: DetectionOptions) -> list[Box]:
    gap = options.max_column_gap
    changed = True
    while changed and gap > 0:
        changed = False
        boxes.sort(key=lambda box: box.min_col)
        by_min_col: dict[int, list[int]] = defaultdict(list)
        for index, box in enumerate(boxes):
            by_min_col[box.min_col].append(index)
        alive = [True] * len(boxes)
        for index, left in enumerate(boxes):
            if not alive[index]:
                continue
            for col in range(left.max_col + 1, left.max_col + 2 + gap):
                for other in by_min_col.get(col, []):
                    right = boxes[other]
                    if other == index or not alive[other]:
                        continue
                    common = min(left.max_row, right.max_row) - max(left.min_row, right.min_row) + 1
                    # A lone column of labels has no values of its own: it belongs to the values beside it
                    # as soon as its rows fall within theirs, even cut into pieces by an empty cell
                    reference = left.height if left.width == 1 else max(left.height, right.height)
                    if common < SIDE_BY_SIDE_ROW_SHARE * reference:
                        continue
                    if _has_own_keys(grid, left, right, options):
                        continue
                    left.absorb(right)
                    alive[other] = False
                    changed = True
        boxes = [box for box, keep in zip(boxes, alive) if keep]
    return boxes


def _bridge_label_blocks(grid: SheetGrid, boxes: list[Box], options: DetectionOptions) -> list[Box]:
    """
    Join a block of row labels to the values it names, however many empty columns lie between them: the
    labels hold text only, their rows are the values' rows (the values' header rows aside), nothing sits
    between the two on those rows, and the values carry no row keys of their own. The alignment row for row
    is what ties them, not the distance.
    """
    by_max_row: dict[int, list[Box]] = defaultdict(list)
    for box in boxes:
        by_max_row[box.max_row].append(box)
    absorbed: set[int] = set()
    for left in sorted(boxes, key=lambda box: box.min_col):
        if id(left) in absorbed:
            continue
        candidates = sorted(
            (box for box in by_max_row[left.max_row]
             if id(box) not in absorbed and box.min_col > left.max_col and box.min_row <= left.min_row),
            key=lambda box: box.min_col,
        )
        right = next(iter(candidates), None)
        if right is None or not _labels_values(grid, left, right, boxes, options):
            continue
        left.absorb(right)
        absorbed.add(id(right))
        by_max_row[left.max_row] = [box for box in by_max_row[left.max_row] if box is not right]
    return [box for box in boxes if id(box) not in absorbed]


def _labels_values(grid: SheetGrid, left: Box, right: Box, boxes: list[Box], options: DetectionOptions) -> bool:
    """Whether the left box is the row labels of the right one (see ``_bridge_label_blocks``)."""
    band = Box(left.min_row, left.max_col + 1, left.max_row, right.min_col - 1)
    if any(grid.count_in(row, band.min_col, band.max_col) for row in range(band.min_row, band.max_row + 1)):
        # Content between the two: another block, or a native table (outside every box)
        return False
    label_rows = grid.content_rows(left)
    value_rows = grid.content_rows(right)
    if len(label_rows) < 2 or not set(label_rows) <= set(value_rows):
        return False
    unlabelled = [row for row in value_rows if row not in set(label_rows)]
    if len(unlabelled) > options.max_header_rows or any(row > label_rows[0] for row in unlabelled):
        return False
    kinds = _column_kinds(grid, left, options)
    if not kinds or any(kind is not Kind.TEXT for kind in kinds):
        return False
    if not any(kind in TYPED_KINDS for kind in _column_kinds(grid, right, options)):
        # Text beside text (two titles, two lists): nothing there for the labels to name
        return False
    if _has_own_keys(grid, left, right, options):
        return False
    # Last, as it reads every box of the sheet: a block whose rectangle crosses the band without a value in it
    return not any(box is not left and box is not right and box.intersects(band) for box in boxes)


def _merge_overlapping(boxes: list[Box]) -> list[Box]:
    changed = True
    while changed:
        changed = False
        boxes.sort(key=lambda box: box.min_row)
        result: list[Box] = []
        active: list[Box] = []
        for box in boxes:
            active = [other for other in active if other.max_row >= box.min_row]
            hit = next((other for other in active if other.intersects(box)), None)
            if hit is None:
                active.append(box)
                result.append(box)
            else:
                hit.absorb(box)
                changed = True
        boxes = result
    return boxes


def _bridge_rows(grid: SheetGrid, boxes: list[Box], options: DetectionOptions) -> list[Box]:
    gap = options.max_row_gap
    if gap <= 0:
        return boxes
    boxes.sort(key=lambda box: (box.min_row, box.min_col))
    by_min_row: dict[int, list[int]] = defaultdict(list)
    for index, box in enumerate(boxes):
        by_min_row[box.min_row].append(index)
    alive = [True] * len(boxes)
    for index, upper in enumerate(boxes):
        if not alive[index]:
            continue
        extended = True
        while extended:
            extended = False
            for row in range(upper.max_row + 1, upper.max_row + 2 + gap):
                for other in by_min_row.get(row, []):
                    lower = boxes[other]
                    if other == index or not alive[other]:
                        continue
                    common = min(upper.max_col, lower.max_col) - max(upper.min_col, lower.min_col) + 1
                    if common < STACKED_COLUMN_SHARE * min(upper.width, lower.width):
                        continue
                    if _continues(grid, upper, lower, options):
                        upper.absorb(lower)
                        alive[other] = False
                        extended = True
                        break
                if extended:
                    break
    return [box for box, keep in zip(boxes, alive) if keep]


def _top_rows(options: DetectionOptions) -> int:
    """
    How many of a box's first rows tell its titles and its header: the title rows, the header rows and
    the body sample they are compared with, plus the one row that says more follow. Reading a box by
    them alone keeps a join's cost off the height of the box it grows.
    """
    return options.max_title_rows + options.max_header_rows + options.sample_rows + 1


def _split_titles(grid: SheetGrid, rows: list[int], box: Box, options: DetectionOptions) -> tuple[list[int], list[int]]:
    """Some first rows of a box, split into those below its title rows and the titles."""
    titles = title_rows(grid, rows, box, options.max_title_rows)
    return rows[len(titles):], titles


def _body_rows(grid: SheetGrid, box: Box, options: DetectionOptions) -> tuple[list[int], list[int]]:
    """A box's first rows (``_top_rows``) below its title rows, and the titles."""
    return _split_titles(grid, grid.content_rows(box, limit=_top_rows(options)), box, options)


def _header_count(grid: SheetGrid, rows: list[int], box: Box, options: DetectionOptions) -> int:
    return header_count(grid, rows, box, options.max_header_rows, options.sample_rows)


def _continues(grid: SheetGrid, upper: Box, lower: Box, options: DetectionOptions) -> bool:
    """Whether the lower box carries on the table of the upper one (see the module docstring, step 3)."""
    upper_rows, _ = _body_rows(grid, upper, options)
    lower_rows, lower_titles = _body_rows(grid, lower, options)
    if not upper_rows or not lower_rows:
        return False
    if all(grid.count_in(row, upper.min_col, upper.max_col) < 2 for row in range(upper_rows[0], upper.max_row + 1)):
        # A block of lone cells is a title or a note, attached later
        return False
    union = Box(upper.min_row, min(upper.min_col, lower.min_col), lower.max_row, max(upper.max_col, lower.max_col))
    if _header_count(grid, upper_rows + lower_rows, union, options) >= len(upper_rows):
        # The upper block is the header of the lower one
        return True
    if _header_count(grid, lower_rows, lower, options):
        return False
    if lower_titles and not _header_count(grid, upper_rows, upper, options):
        # Sections share the column names written on top of a table; a titled block under a block
        # without any is a sibling block
        return False
    sample = lower_rows[:options.sample_rows]
    return _same_shape(grid, upper, sample[:1], lower, options) and (
        len(sample) < 2 or _same_shape(grid, upper, sample[1:], lower, options))


def _same_shape(grid: SheetGrid, upper: Box, rows: list[int], lower: Box, options: DetectionOptions) -> bool:
    """
    Whether some rows of the lower box (their type per column) have the shape of the rows above: text where
    they hold text, values where they hold values. A number under a date is not a mismatch.
    """
    upper_rows = grid.last_content_rows(upper, options.sample_rows)
    columns = sorted({col for row in rows for col in grid.columns_in(row, lower.min_col, lower.max_col)})
    matches = mismatches = 0
    for col in columns:
        if not upper.min_col <= col <= upper.max_col:
            continue
        above, _ = dominant_kind(grid, col, upper_rows, HEADER_TYPE_SHARE)
        kind, _ = dominant_kind(grid, col, rows, HEADER_TYPE_SHARE)
        if above is None or kind is None or kind is Kind.ERROR:
            continue
        if (above is Kind.TEXT) == (kind is Kind.TEXT):
            matches += 1
        else:
            mismatches += 1
    return matches > mismatches or not mismatches


def _split_at_inner_headers(grid: SheetGrid, box: Box, options: DetectionOptions) -> list[Box]:
    """
    Cut a region where a new table starts below data rows (see the module docstring, step 4).

    A region is cut again and again from the top (a paginated export repeats its header every page), so
    what each cut reads of the rest is kept up to date instead of read again: the rest's rows are the
    region's rows from the cut on, its columns come from the rows' own extents, and its columns' types
    from counts the rows cut off are taken out of. The whole costs one reading of the region's cells.
    """
    rows = grid.content_rows(box)
    extents = [grid.row_extent(row, box.min_col, box.max_col) for row in rows]
    # The box of the rows from each index on: the rest of the region after a cut there
    rests: list[Optional[Box]] = [None] * (len(rows) + 1)
    for index in range(len(rows) - 1, -1, -1):
        rest = Box(extents[index].min_row, extents[index].min_col, extents[index].max_row, extents[index].max_col)
        if rests[index + 1] is not None:
            rest.absorb(rests[index + 1])
        rests[index] = rest
    counts = column_kind_counts(grid, rows, box.min_col, box.max_col)

    parts: list[Box] = []
    current, first = box, 0
    while True:
        cut = _inner_header(grid, current, rows, first, counts, options)
        if cut is None:
            parts.append(current)
            return parts
        above = rows[first:cut]
        upper = grid.shrink(above, current.min_col, current.max_col)
        if upper is not None:
            parts.append(upper)
        for row in above:
            for col in grid.columns_in(row, box.min_col, box.max_col):
                counts[col][grid.kinds[(row, col)]] -= 1
        first, current = cut, rests[cut]


def _inner_header(
    grid: SheetGrid, box: Box, rows: list[int], first: int, counts: dict[int, dict[Kind, int]],
    options: DetectionOptions,
) -> Optional[int]:
    """
    The index, in ``rows``, of the row where a new table starts inside a region: a header row below data
    rows, either under a title row (the cut then falls on the title) or repeating the region's top header,
    type by type.

    Args:
        grid: The sheet's cells
        box: The region
        rows: Content rows, the region's being those from ``first`` on
        first: The index of the region's first row in ``rows``
        counts: The cells of each kind the region's columns hold (``column_kind_counts``)
        options: Detection thresholds
    """
    top_rows, titles = _split_titles(grid, rows[first:first + _top_rows(options)], box, options)
    if not top_rows:
        return None
    start = first + len(titles) + _header_count(grid, top_rows, box, options)
    top = top_rows[0]
    # Cheap filter: a header row holds at least one cell of another type than its column's, region-wide
    region = {col: dominant_of(kinds, HEADER_TYPE_SHARE)[0] for col, kinds in counts.items()}
    for index in range(start + 1, len(rows) - 1):
        row = rows[index]
        cols = grid.columns_in(row, box.min_col, box.max_col)
        if len(cols) < 2 or all(grid.kind(row, col) is region[col] for col in cols):
            continue
        body = rows[index + 1:index + 1 + options.sample_rows]
        if not is_header_row(grid, row, box.min_col, box.max_col, body, first=False, formatting=False):
            continue
        previous = rows[index - 1]
        count = grid.count_in(previous, box.min_col, box.max_col)
        dense = grid.count_in(row, box.min_col, box.max_col) >= DENSE_ROW_FACTOR * count
        if previous == row - 1 and count <= sparse_row_count(box) and dense:
            return index - 1
        cols = [col for col in grid.columns_in(row, box.min_col, box.max_col) if grid.kind(row, col) is not None]
        odd = [col for col in cols if grid.kind(row, col) is not grid.kind(body[0], col)] if body else []
        if len(odd) >= 2 and all(grid.kind(top, col) is grid.kind(row, col) for col in odd):
            return index
    return None
