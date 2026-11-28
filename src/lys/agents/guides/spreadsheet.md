# Spreadsheet table detection (back)

`lys.core.utils.spreadsheet` reads an `.xlsx` / `.xlsm` workbook and describes the tables of each
sheet: where each table sits, its title, its header rows and column labels, its label column, the
dominant type of each column, and how it reads (its nature). It is deterministic and content-agnostic,
in the spirit of a dataframe description: no AI, no knowledge of what the cells mean.

Plain functions on top of `openpyxl` (no app, no registry, no database): usable from the API, a
Celery task or a script.

## Entry points

```python
from lys.core.utils.spreadsheet import detect_tables, DetectionOptions

result = detect_tables(content)                      # bytes, a path, or a binary stream
result = detect_tables(path, sheet_names=["Plan"])   # some sheets only
result = detect_tables(content, options=DetectionOptions(max_row_gap=1))
```

| Function | Input | Use it when |
|----------|-------|-------------|
| `detect_tables(source, *, sheet_names, options)` | bytes, `str` / `Path`, binary stream | the default: it opens the workbook itself, with the fallbacks below |
| `detect_workbook_tables(workbook, *, sheet_names, options)` | an open openpyxl workbook | the caller already holds the workbook |
| `detect_sheet_tables(sheet, *, index, options)` | one worksheet or chart sheet | one sheet only |

`detect_tables` opens the workbook with the values the spreadsheet saved (`data_only=True`: formulas
are not evaluated, macros never run), in normal mode. When openpyxl cannot parse a part the detector
does not need (observed: a pivot cache with a manually grouped field), it retries on an in-memory copy
without the pivot references, then falls back to read-only mode (`WorkbookTables.read_only = True`).
A file that opens in no mode raises the error of the first attempt.

## Output

```
WorkbookTables
├── read_only: bool                    opened read-only: no merged ranges, fonts, native tables
└── sheets: list[SheetTables]
    ├── name, index, kind (worksheet | chartsheet), hidden, read_only
    ├── notes: list[SheetNote]         cells outside every table and title (ref, text), first max_notes
    ├── notes_total
    └── tables: list[DetectedTable]
        ├── sheet, source (native | region), name (Excel table name, native only)
        ├── range: CellRange           header rows + data rows, title excluded
        ├── title, title_refs          title lines joined with a line break, and their cells
        ├── header_rows: list[int]
        ├── columns: list[TableColumn] every column of the range, empty ones included
        │   ├── index, letter
        │   ├── header: list[value]    raw header value per header row (a merged cell repeated over its span)
        │   ├── label                  header texts joined with " / " ("2026 / Capital")
        │   ├── header_type            type of the lowest non-empty header value
        │   ├── dtype                  dominant type of the data cells: text | number | date | bool | mixed | empty
        │   └── non_empty_count
        ├── label_column, row_labels   the row-label column and its texts (None / [] for a record list)
        ├── data_range, data_row_count
        ├── nature                     time_series | record_list | key_value | other
        └── sequences: list[SequenceRun]
            └── orientation (columns | rows), line, first, last, kind (date | number | numbered_text), length
```

`CellRange` gives `min_row`, `min_col`, `max_row`, `max_col` (1-based, inclusive), `height`, `width`
and `ref` (`"A3:P20"`). All models are frozen pydantic models: `model_dump()` gives a JSON-ready dict
(dates excepted: use `model_dump(mode="json")`).

**Cell values are not returned**, header values aside. The caller reads the data it needs from the
ranges, with the workbook it already holds:

```python
from openpyxl import load_workbook

workbook = load_workbook(path, data_only=True, read_only=True)
sheet = workbook[table.sheet]
for row in sheet.iter_rows(min_row=table.data_range.min_row, max_row=table.data_range.max_row,
                           min_col=table.data_range.min_col, max_col=table.data_range.max_col,
                           values_only=True):
    ...
```

## Natures

The nature is read from the structure once the table is found; it never decides whether a table or a
header exists.

| Nature | Structure | Read it as |
|--------|-----------|------------|
| `time_series` | an ordered run covers at least half of the value columns of a header row (dates, integers with a constant step, labels like "S1", "S2"), or a leading date column increases down the rows beside numeric columns | the axis is in `sequences`: `orientation`, the header row (`line`) or column, `first` / `last` |
| `key_value` | a label column and at most 3 other columns, at most one of them typed | pairs: `row_labels` and the value column |
| `record_list` | a header, and none of the above | one row = one record described by `columns` |
| `other` | no header, no run, no label/value pair | a grid: read the columns' types |

What a sequence *means* (months, years, weeks, a fiscal calendar) is the caller's: the detector says
"ordered dates / integers / numbered labels", the caller reads `columns[].header` to name the period.

## How tables and headers are found

Structure only, never what the cells say:

- **Regions**: connected non-empty cells (a merged range counts as filled), then joins repeated until
  nothing changes. Side by side, a block joins the one on its left unless it has its own row keys (it
  starts with a column of text or dates followed by values). Farther apart, a block of text alone joins
  the values on its right when it labels them row for row (same rows, the values' header rows aside)
  with nothing in between: the alignment ties them, not the distance. Stacked, a block joins the one above when
  the upper one is its header, or when it opens on no header and its body has the same shape; a titled
  block joins only a table whose header its sections can share.
- **Header**: a header cell is the odd one out of its column (a type the body almost never holds
  there); at a table's top an ordered run the body does not repeat also heads it. The header is a
  contiguous run of such rows from the top; its first row may be atypical (codes, units). A row
  repeating a label in adjacent columns heads the table only as a level of groups over a row naming
  the columns. One definition, used by every step.
- **New table inside a region**: a header row below data rows, under a title row or repeating the
  region's top header type by type.
- **Title**: sparse rows on top of a region followed by a denser row; never an ordered run nor a
  merged group label.

The rules and their thresholds are documented in `rules.py` and `segmentation.py` (module docstrings
and named constants at the top).

## RULES

- **R1 — Bound the input upstream.** The workbook is loaded fully in memory. A caller exposing user
  uploads limits the file size and its uncompressed size before calling, as for `lys.core.utils.ingest`.
  Detection time grows with the number of values, not with the area a sheet spans; a sheet made of
  hundreds of thousands of isolated cells still costs far more than a dense one of the same size, so
  an upload is detected off the request path, in a task with a time limit.
- **R2 — Business meaning stays with the caller.** Years, months, fiscal periods, units: derive them
  from `columns[].header` and `sequences` in the consuming app. Never add a vocabulary of periods, a
  year range or a sheet name to the detector.
- **R3 — Read `read_only`.** When `True`, titles in merged cells, bold headers over text-only columns
  and Excel table objects are not recognised as such: tell the user the reading is degraded rather
  than presenting it as complete.
- **R4 — Do not re-segment.** Consume the ranges as given. A table that comes out wrong is a detector
  issue: fix it there (R6), not with a caller-side patch that would diverge from the next reader.
- **R5 — Options are thresholds, not switches.** `DetectionOptions` tunes gaps and sample sizes; the
  defaults suit hand-made workbooks. Change them for a whole family of files, never per file.
- **R6 — A fix is a principle, not a case.** A misread layout is corrected by the structural rule it
  breaks, simplified or replaced when it is the cause. A rule that would only hold for one file is not
  written: it is listed under the known limits below. Every rule comes with a unit test on a workbook
  built in memory with openpyxl, with invented data, and the change is checked for regressions on the
  workbooks already measured.

## Known limits

- Two plain consecutive integers over amounts ("Line | 2026 | 2027") are not told from a row of figures:
  the run of two counts as a header only in bold over plain rows. Two numbered labels ("Budget 2026 |
  Budget 2027") never make an axis; three and more do.
- A section separated from its header by more empty rows than `max_row_gap` comes out as a table of its
  own, without a header.
- After a blank row, a row of integers with a constant step (10, 11, 12) can be read as a new header.
- Month names written as text ("Jan", "janv.") are not an ordered run; months entered as dates are.
- A record list cut by an empty column whose right part starts with a column of dates comes out as two
  tables.
- A merged header cell repeats its value over every column it spans (`header`, `label`), by design.
- Formulas never calculated by Excel (a file written by a script) read as empty cells.

## Tests

`tests/unit/core/utils/test_spreadsheet.py` builds every case in memory. Run only that module:

```bash
pytest tests/unit/core/utils/test_spreadsheet.py
```
