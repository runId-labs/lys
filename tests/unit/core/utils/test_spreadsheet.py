"""
Unit tests for lys.core.utils.spreadsheet — workbooks built in memory with openpyxl, invented data.
"""
import io
import zipfile
from datetime import datetime
from unittest.mock import patch

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table

from lys.core.utils.spreadsheet import (
    CellType,
    DetectionOptions,
    SequenceKind,
    SequenceOrientation,
    SheetKind,
    TableNature,
    TableSource,
    detect_sheet_tables,
    detect_tables,
)
from lys.core.utils.spreadsheet import loading
from lys.core.utils.spreadsheet.grid import Box, Kind, SheetGrid
from lys.core.utils.spreadsheet.loading import without_pivot_tables
from lys.core.utils.spreadsheet.rules import column_kind_counts, dominant_kind, dominant_of, sequence_runs

BOLD = Font(bold=True)


def _to_bytes(workbook: Workbook) -> bytes:
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _sheet(workbook: Workbook, title: str = "Sheet"):
    sheet = workbook.active
    sheet.title = title
    return sheet


def _write(sheet, top_row: int, left_col: int, rows: list[list]) -> None:
    for row_offset, values in enumerate(rows):
        for col_offset, value in enumerate(values):
            if value is not None:
                sheet.cell(row=top_row + row_offset, column=left_col + col_offset, value=value)


def _detect(workbook: Workbook, **kwargs):
    """Round-trip through bytes, as a caller reading an upload does."""
    return detect_tables(_to_bytes(workbook), **kwargs)


def _only_sheet(workbook: Workbook):
    result = _detect(workbook)
    assert len(result.sheets) == 1
    return result.sheets[0]


class TestEmptyColumnInsideTable:
    def test_label_column_then_empty_column_then_values_is_one_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 4, 1, [["Line"] + [None] + [f"P{n}" for n in range(1, 14)] + ["Total"]])
        for offset, label in enumerate(["Sales", "Services", "Rent", "Wages", "Net"]):
            row = 5 + offset
            sheet.cell(row=row, column=1, value=label)
            for col in range(3, 17):
                sheet.cell(row=row, column=col, value=float(offset * 100 + col))

        tables = _only_sheet(workbook).tables

        assert len(tables) == 1
        table = tables[0]
        assert table.range.ref == "A4:P9"
        assert table.label_column == 1
        assert table.header_rows == [4]
        assert [label.label for label in table.row_labels] == ["Sales", "Services", "Rent", "Wages", "Net"]
        assert table.columns[1].dtype is CellType.EMPTY
        assert table.columns[2].label == "P1"
        assert table.columns[2].dtype is CellType.NUMBER

    def test_blank_rows_between_sections_do_not_cut_the_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Item", "Q1", "Q2", "Q3", "Q4"]])
        _write(sheet, 2, 1, [["INFLOWS"]])
        _write(sheet, 3, 1, [["Sales", 10, 11, 12, 13], ["Grants", 1, 1, 1, 1]])
        _write(sheet, 6, 1, [["OUTFLOWS"]])
        _write(sheet, 7, 1, [["Rent", 5, 5, 5, 5], ["Wages", 4, 4, 4, 4]])
        _write(sheet, 10, 1, [["Closing", 2, 6, 4, 5], ["Status", "ok", "ok", "low", "ok"], ["Margin", 1, 1, 2, 2]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:E12"]
        assert tables[0].header_rows == [1]
        assert tables[0].nature is TableNature.TIME_SERIES
        assert "OUTFLOWS" in [label.label for label in tables[0].row_labels]

    def test_tables_side_by_side_each_with_its_labels_stay_apart(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        left = [["Entity A", 2024, 2025, 2026], ["Sales", 1, 2, 3], ["Costs", 4, 5, 6]]
        right = [["Entity B", 2024, 2025, 2026], ["Sales", 7, 8, 9], ["Costs", 1, 2, 3]]
        _write(sheet, 1, 1, left)
        _write(sheet, 1, 6, right)

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:D3", "F1:I3"]
        assert all(table.label_column == table.range.min_col for table in tables)

    def test_comment_column_after_a_gap_joins_the_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Label", "Amount", None, "Comment"], ["Fees", 12, None, "estimated"],
                             ["Tax", 3, None, "paid"], ["Misc", 1, None, "to check"]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:D4"]


class TestTitles:
    def test_single_cell_title_is_detached_from_the_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Signed quotes"]])
        _write(sheet, 2, 1, [["Ref", "Customer", "Date", "Amount"]])
        for index in range(20):
            _write(sheet, 3 + index, 1, [[f"Q-{index}", f"Customer {index % 4}", datetime(2026, 1, 1 + index),
                                          100.0 + index]])

        table = _only_sheet(workbook).tables[0]

        assert table.title == "Signed quotes"
        assert table.title_refs == ["A1"]
        assert table.range.ref == "A2:D22"
        assert table.header_rows == [2]
        assert [column.label for column in table.columns] == ["Ref", "Customer", "Date", "Amount"]

    def test_merged_two_line_title_is_detached_and_the_range_shrinks(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Monthly revenue"], ["Amounts excluding tax"]])
        sheet.merge_cells("A1:H1")
        sheet.merge_cells("A2:H2")
        _write(sheet, 3, 1, [["Product", "Units", "Amount"], ["Alpha", 3, 30.0], ["Beta", 4, 52.5],
                             ["Gamma", 1, 9.9]])

        table = _only_sheet(workbook).tables[0]

        assert table.title == "Monthly revenue\nAmounts excluding tax"
        assert table.range.ref == "A3:C6"
        assert table.header_rows == [3]

    def test_title_block_above_a_blank_row_is_attached(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Cash plan"]])
        _write(sheet, 3, 1, [["Line", "M1", "M2", "M3"], ["Sales", 1, 2, 3], ["Costs", 3, 2, 1]])

        sheet_tables = _only_sheet(workbook)

        assert sheet_tables.tables[0].title == "Cash plan"
        assert sheet_tables.notes == []

    def test_titled_table_written_right_under_another_starts_a_new_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Month", datetime(2026, 1, 1), datetime(2026, 2, 1), datetime(2026, 3, 1)],
                             ["Sales", 1, 2, 3], ["Costs", 2, 2, 2]])
        _write(sheet, 4, 1, [["Chart data"]])
        _write(sheet, 5, 1, [["Series", datetime(2026, 1, 1), datetime(2026, 2, 1), datetime(2026, 3, 1)],
                             ["Balance", 5, 6, 7]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:D3", "A5:D6"]
        assert tables[1].title == "Chart data"


class TestSummaryThenList:
    def test_summary_and_list_separated_by_a_blank_row_are_two_tables(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Bucket", "Amount", "Count"], ["0-30 days", 1200.0, 12], ["31-60 days", 800.0, 7],
                             ["61-90 days", 150.0, 2], ["> 90 days", 90.0, 1]])
        _write(sheet, 7, 1, [["Customer", "Invoice", "Issued", "Due", "Amount", "Status"]])
        for index in range(450):
            _write(sheet, 8 + index, 1, [[f"Customer {index % 37}", f"INV-{index:04d}", datetime(2026, 1, 1),
                                          datetime(2026, 2, 1), float(index), "open" if index % 3 else "late"]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:C5", "A7:F457"]
        summary, records = tables
        assert summary.header_rows == [1]
        assert records.header_rows == [7]
        assert records.nature is TableNature.RECORD_LIST
        assert records.data_row_count == 450
        assert records.label_column is None and records.row_labels == []
        assert [column.dtype for column in records.columns] == [
            CellType.TEXT, CellType.TEXT, CellType.DATE, CellType.DATE, CellType.NUMBER, CellType.TEXT]


class TestHeaders:
    def test_date_header_cells_make_a_time_series(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        months = [datetime(2026, month, 1) for month in range(1, 13)]
        _write(sheet, 1, 1, [["Revenue"] + months])
        for offset, label in enumerate(["Product A", "Product B", "Total"]):
            _write(sheet, 2 + offset, 1, [[label] + [float(offset + month) for month in range(12)]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1]
        assert table.nature is TableNature.TIME_SERIES
        assert table.columns[1].header == [months[0]]
        assert table.columns[1].header_type is CellType.DATE
        assert table.columns[1].label == "2026-01-01"
        run = table.sequences[0]
        assert (run.orientation, run.line, run.first, run.last, run.kind) == (
            SequenceOrientation.COLUMNS, 1, 2, 13, SequenceKind.DATE)

    def test_integer_header_over_numbers_is_a_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [[None, 2024, 2025, 2026], ["Sales", 100, 120, 130], ["Margin", 30, 35, 41]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1]
        assert table.nature is TableNature.TIME_SERIES
        assert table.sequences[0].kind is SequenceKind.NUMBER

    def test_numbered_labels_with_a_total_column(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Week"] + [f"W{n}" for n in range(1, 9)] + ["Total"]])
        _write(sheet, 2, 1, [["Opening", 1, 2, 3, 4, 5, 6, 7, 8, 36], ["Closing", 2, 3, 4, 5, 6, 7, 8, 9, 44]])

        table = _only_sheet(workbook).tables[0]

        assert table.nature is TableNature.TIME_SERIES
        assert [(run.first, run.last, run.kind) for run in table.sequences] == [(2, 9, SequenceKind.NUMBERED_TEXT)]

    def test_merged_group_header_is_repeated_over_its_columns(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Region", "Actual", None, None, "Budget"], ["", "Q1", "Q2", "Q3", "Q1"]])
        sheet.merge_cells("B1:D1")
        _write(sheet, 3, 1, [["North", 1, 2, 3, 4], ["South", 5, 6, 7, 8], ["East", 1, 1, 1, 1]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1, 2]
        assert [column.label for column in table.columns] == ["Region", "Actual / Q1", "Actual / Q2",
                                                              "Actual / Q3", "Budget / Q1"]
        assert table.title is None

    def test_text_only_table_with_bold_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Name", "Team", "City"], ["Ana", "Ops", "Lyon"], ["Ben", "Ops", "Nantes"],
                             ["Cleo", "Sales", "Lille"]])
        for col in range(1, 4):
            sheet.cell(row=1, column=col).font = BOLD

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1]
        assert table.nature is TableNature.RECORD_LIST

    def test_text_only_table_without_formatting_uses_its_distinct_first_row(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Code", "Meaning"], ["A", "Active"], ["S", "Suspended"], ["C", "Closed"]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1]

    def test_a_single_date_among_values_is_not_a_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Period start", datetime(2026, 1, 1)], ["Budget", 1000.0], ["Spent", 420.0],
                             ["Remaining", 580.0]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == []
        assert table.nature is TableNature.KEY_VALUE


class TestNatures:
    def test_key_value_block_with_a_comment_column(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Indicator", "Value", "Note"], ["Headcount", 12, "end of month"],
                             ["Turnover rate", 0.08, None], ["Open positions", 2, "two interviews"]])

        table = _only_sheet(workbook).tables[0]

        assert table.nature is TableNature.KEY_VALUE
        assert table.label_column == 1
        assert [label.label for label in table.row_labels] == ["Headcount", "Turnover rate", "Open positions"]

    def test_leading_date_column_makes_a_time_series_by_rows(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Month", "Low", "Mid", "High"]])
        for month in range(1, 13):
            _write(sheet, 1 + month, 1, [[datetime(2026, month, 1), month * 1.0, month * 2.0, month * 3.0]])

        table = _only_sheet(workbook).tables[0]

        assert table.nature is TableNature.TIME_SERIES
        assert table.label_column is None
        run = table.sequences[0]
        assert (run.orientation, run.line, run.first, run.last) == (SequenceOrientation.ROWS, 1, 2, 13)

    def test_list_with_an_increasing_id_column_stays_a_record_list(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Id", "Customer", "Amount"]])
        for index in range(1, 30):
            _write(sheet, 1 + index, 1, [[index, f"Customer {index}", index * 10.0]])

        table = _only_sheet(workbook).tables[0]

        assert table.nature is TableNature.RECORD_LIST

    def test_grid_without_header_is_other(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [[1, 2, 3], [4, 5, 6], [7, 8, 9]])

        table = _only_sheet(workbook).tables[0]

        assert table.nature is TableNature.OTHER
        assert table.header_rows == []


class TestSheetsAndSources:
    def test_chart_sheet_is_reported_without_tables(self):
        workbook = Workbook()
        sheet = _sheet(workbook, "Data")
        _write(sheet, 1, 1, [["Month", "Amount"], ["Jan", 1], ["Feb", 2], ["Mar", 3]])
        chart = BarChart()
        chart.add_data(Reference(sheet, min_col=2, min_row=1, max_row=4), titles_from_data=True)
        chart_sheet = workbook.create_chartsheet("Chart")
        chart_sheet.add_chart(chart)

        result = _detect(workbook)

        kinds = {sheet.name: sheet.kind for sheet in result.sheets}
        assert kinds == {"Data": SheetKind.WORKSHEET, "Chart": SheetKind.CHARTSHEET}
        assert result.sheets[1].tables == []
        assert len(result.tables) == 1

    def test_empty_sheet_and_hidden_sheet(self):
        workbook = Workbook()
        _sheet(workbook, "Empty")
        hidden = workbook.create_sheet("Hidden")
        hidden.sheet_state = "hidden"
        _write(hidden, 1, 1, [["Key", "Value"], ["Rate", 0.2], ["Cap", 10]])

        result = _detect(workbook)

        assert result.sheets[0].tables == [] and result.sheets[0].notes == []
        assert result.sheets[1].hidden is True
        assert result.sheets[1].index == 1
        assert len(result.sheets[1].tables) == 1

    def test_sheet_names_filter(self):
        workbook = Workbook()
        _sheet(workbook, "First")
        workbook.create_sheet("Second")

        result = _detect(workbook, sheet_names=["Second"])

        assert [sheet.name for sheet in result.sheets] == ["Second"]
        assert result.sheets[0].index == 1

    def test_native_table_is_read_from_the_file(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 2, 2, [["Sku", "Stock"], ["X1", 4], ["X2", 0], ["X3", 9]])
        sheet.add_table(Table(displayName="Stock", ref="B2:C5"))
        _write(sheet, 8, 2, [["Loose", "cells"], ["a", 1], ["b", 2]])

        tables = _only_sheet(workbook).tables

        native = next(table for table in tables if table.source is TableSource.NATIVE)
        assert native.name == "Stock"
        assert native.range.ref == "B2:C5"
        assert native.header_rows == [2]
        assert [column.label for column in native.columns] == ["Sku", "Stock"]
        assert any(table.source is TableSource.REGION for table in tables)

    def test_stray_cells_are_notes(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Key", "Value"], ["Rate", 0.2], ["Cap", 10]])
        sheet["H20"] = "Figures are indicative"

        sheet_tables = _only_sheet(workbook)

        assert [(note.ref, note.text) for note in sheet_tables.notes] == [("H20", "Figures are indicative")]
        assert sheet_tables.notes_total == 1

    def test_read_only_worksheet_is_supported(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", 2024, 2025, 2026], ["Sales", 10, 14, 13], ["Costs", 3, 5, 4]])
        read_only = load_workbook(io.BytesIO(_to_bytes(workbook)), read_only=True, data_only=True)
        try:
            sheet_tables = detect_sheet_tables(read_only["Sheet"])
        finally:
            read_only.close()

        assert sheet_tables.tables[0].range.ref == "A1:D3"
        assert sheet_tables.tables[0].nature is TableNature.TIME_SERIES

    def test_many_sheets_of_long_lists(self):
        workbook = Workbook()
        _sheet(workbook, "S0")
        for index in range(1, 30):
            workbook.create_sheet(f"S{index}")
        for sheet in workbook.worksheets:
            _write(sheet, 1, 1, [["Date", "Label", "Debit", "Credit"]])
            for row in range(2, 402):
                sheet.cell(row=row, column=1, value=datetime(2026, 1, 1 + row % 28))
                sheet.cell(row=row, column=2, value=f"Entry {row}")
                sheet.cell(row=row, column=3, value=float(row))

        result = _detect(workbook)

        assert len(result.tables) == 30
        # The header names a fourth column that holds no data yet: it stays in the table, typed EMPTY
        assert all(table.range.ref == "A1:D401" and table.data_row_count == 400 for table in result.tables)
        assert all(table.columns[3].dtype is CellType.EMPTY for table in result.tables)

    def test_options_are_applied(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", "M1", "M2"], ["Sales", 1, 2]])
        _write(sheet, 4, 1, [["Rent", 3, 4]])

        joined = _detect(workbook).tables
        apart = _detect(workbook, options=DetectionOptions(max_row_gap=0)).tables

        assert [table.range.ref for table in joined] == ["A1:C4"]
        # A single row is not a table: it becomes notes
        assert [table.range.ref for table in apart] == ["A1:C2"]


class TestStackedAndSideBySide:
    def test_side_by_side_tables_with_a_code_column_before_their_labels_stay_apart(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", 2024, 2025, 2026], ["Sales", 10, 14, 13], ["Costs", 3, 5, 4],
                             ["Margin", 7, 9, 9]])
        _write(sheet, 1, 6, [[None, "Line", 2024, 2025, 2026], [101, "Sales", 8, 9, 7], [102, "Costs", 2, 3, 2],
                             [103, "Margin", 6, 6, 5]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:D4", "F1:J4"]

    def test_header_of_several_rows_codes_names_then_years(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [[None, 11, 12, 13], [None, "North", "South", "East"], ["Line", 2024, 2025, 2026],
                             ["Sales", 10.5, 14.2, 13.1], ["Costs", 3.2, 5.9, 4.4]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1, 2, 3]
        assert table.columns[1].label == "11 / North / 2024"

    def test_merged_group_label_over_a_row_of_years(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 2, [["Entity A"]])
        sheet.merge_cells("B1:D1")
        _write(sheet, 2, 1, [["Line", 2024, 2025, 2026], ["Sales", 10.5, 14.2, 13.1], ["Costs", 3.2, 5.9, 4.4]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1, 2]
        assert table.nature is TableNature.TIME_SERIES
        assert table.columns[1].label == "Entity A / 2024"

    def test_year_header_after_a_blank_row_starts_a_new_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", 2024, 2025, 2026], ["Sales", 10.5, 14.2, 13.1], ["Costs", 3.2, 5.9, 4.4]])
        _write(sheet, 5, 1, [["Ratio", 2027, 2028, 2029], ["Sales", 11.5, 12.2, 15.1], ["Costs", 3.8, 4.9, 4.1]])

        tables = _only_sheet(workbook).tables

        assert [(table.range.ref, table.header_rows) for table in tables] == [("A1:D3", [1]), ("A5:D7", [5])]

    def test_title_with_a_value_right_under_a_table_starts_a_new_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        months = [datetime(2026, month, 1) for month in range(1, 9)]
        _write(sheet, 1, 1, [["Month"] + months, ["Sales"] + [float(n) for n in range(8)]])
        _write(sheet, 3, 1, [["Chart data", None, None, None, None, None, None, None, 4.5]])
        _write(sheet, 4, 1, [["Series"] + months, ["Balance"] + [float(n) for n in range(8)]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:I2", "A4:I5"]
        assert tables[1].title == "Chart data 4.5"

    def test_header_repeated_under_data_rows_starts_a_new_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        first = [datetime(2026, month, 1) for month in range(1, 7)]
        second = [datetime(2027, month, 1) for month in range(1, 7)]
        _write(sheet, 1, 1, [[None] + first, ["Sales"] + [1.5] * 6, ["Costs"] + [0.5] * 6])
        _write(sheet, 4, 1, [["Next year"] + second, ["Sales"] + [2.5] * 6, ["Costs"] + [1.5] * 6])

        tables = _only_sheet(workbook).tables

        assert [(table.range.ref, table.header_rows) for table in tables] == [("A1:G3", [1]), ("A4:G6", [4])]

    def test_a_row_of_dates_under_a_header_of_years_is_data(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", 2024, 2025, 2026], ["Sales", 10.5, 14.2, 13.1],
                             ["Closing", datetime(2024, 12, 31), datetime(2025, 12, 31), datetime(2026, 12, 31)],
                             ["Costs", 3.2, 5.9, 4.4]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:D4"]

    def test_titled_blocks_without_column_names_are_siblings(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Section one"], ["Rate", 0.2, "fixed"], ["Cap", 10.0, None], ["Floor", 2.0, None]])
        _write(sheet, 6, 1, [["Section two"], ["Delay", 30.0, "days"], ["Fee", 12.5, None]])

        tables = _only_sheet(workbook).tables

        assert [(table.range.ref, table.title) for table in tables] == [
            ("A2:C4", "Section one"), ("A7:C8", "Section two")]
        assert all(table.nature is TableNature.KEY_VALUE for table in tables)

    def test_titled_block_whose_body_is_text_is_not_a_section_of_a_numeric_table(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", "Q1", "Q2", "Q3"], ["Sales", 10.5, 14.2, 13.1], ["Costs", 3.2, 5.9, 4.4]])
        _write(sheet, 5, 1, [["Comments"], ["Sales", 11.0, 12.0, 13.0], ["Note", "high", "flat", "low"],
                             ["Owner", "Ana", "Ben", "Cleo"], ["Status", "draft", "sent", "done"]])

        tables = _only_sheet(workbook).tables

        assert tables[0].range.ref == "A1:D3"


class TestPrinciples:
    def test_text_in_a_column_that_often_holds_text_is_not_a_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Holder", 2021, 2022, 2023]])
        rows = [["Ana", 10, "n/a", 4], ["Ben", 20, 5, "n/a"], ["Subtotal", 30, "n/a", "n/a"], ["Cleo", 5, 3, 2],
                ["Dan", 7, "n/a", 1], ["Total", 42, 8, "n/a"]]
        _write(sheet, 2, 1, rows)

        tables = _only_sheet(workbook).tables

        assert [(table.range.ref, table.header_rows) for table in tables] == [("A1:D7", [1])]

    def test_years_merged_over_three_columns_and_sub_columns_under_them(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        top = ["Loan", "Rate", None]
        for year in (2026, 2027, 2028):
            top += [year, None, None]
        _write(sheet, 1, 1, [top, [None, None, None] + ["Capital", "Interest", "Total"] * 3])
        for col in (4, 7, 10):
            sheet.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + 2)
        _write(sheet, 3, 1, [["Bank A", 0.02, None] + [10.5, 1.2, 11.7] * 3,
                             ["Bank B", 0.03, None] + [20.5, 2.2, 22.7] * 3])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1, 2]
        assert table.nature is TableNature.TIME_SERIES
        assert (table.sequences[0].first, table.sequences[0].last) == (4, 12)
        assert table.columns[3].label == "2026 / Capital"

    def test_header_block_split_from_its_body_by_merged_cells_joins_it(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 2, [["Line", "Rate", 2026, None, 2027, None]])
        sheet.merge_cells("D1:E1")
        sheet.merge_cells("F1:G1")
        _write(sheet, 2, 4, [["Capital", "Interest", "Capital", "Interest"]])
        _write(sheet, 3, 2, [["Bank A", 0.02], ["Bank B", 0.03]])
        _write(sheet, 5, 2, [["Bank C", 0.01, 3.5, 0.2, 3.1, 0.1], ["Total", None, 3.5, 0.2, 3.1, 0.1]])

        tables = _only_sheet(workbook).tables

        assert [(table.range.ref, table.header_rows) for table in tables] == [("B1:G6", [1, 2])]

    def test_group_labels_repeated_in_each_column_over_distinct_years(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [[None, "North", "North", "North", "South", "South", "South"],
                             ["Line", 2024, 2025, 2026, 2024, 2025, 2026],
                             ["Sales", 10.5, 14.2, 13.1, 8.5, 9.2, 9.1], ["Costs", 3.2, 5.9, 4.4, 2.1, 2.2, 2.0]])

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1, 2]

    def test_a_row_of_repeated_statuses_under_data_is_not_a_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Line", "Q1", "Q2", "Q3", "Q4"], ["Sales", 10.5, 14.2, 13.1, 9.9],
                             ["Status", "late", "late", "ok", "ok"], ["Costs", 3.2, 5.9, 4.4, 4.1]])

        table = _only_sheet(workbook).tables[0]

        assert (table.range.ref, table.header_rows) == ("A1:E4", [1])

    def test_label_column_cut_by_an_empty_cell_joins_its_values(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Year"], [None], ["Fees"], ["Travel"]])
        _write(sheet, 1, 4, [[2024, 2025, 2026], [None, 1.5, 2.5], [10.5, 11.2, 12.9], [3.1, 2.9, 3.3]])

        tables = _only_sheet(workbook).tables

        assert [(table.range.ref, table.label_column) for table in tables] == [("A1:F4", 1)]

    @staticmethod
    def _far_labels(label_rows: list[list]) -> Workbook:
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 2, label_rows)
        _write(sheet, 1, 8, [[2026, 2027, 2028], [10.5, 11.2, 12.9], [3.1, 2.9, 3.3], [13.6, 14.1, 16.2]])
        return workbook

    def test_labels_far_from_their_values_with_nothing_between_join_them(self):
        tables = _only_sheet(self._far_labels([["Unit"], ["Fees"], ["Travel"], ["Total"]])).tables

        assert len(tables) == 1
        table = tables[0]
        assert (table.range.ref, table.label_column, table.nature) == ("B1:J4", 2, TableNature.TIME_SERIES)
        assert [label.label for label in table.row_labels] == ["Fees", "Travel", "Total"]
        assert table.columns[0].label == "Unit"

    def test_labels_far_from_values_join_them_without_a_header_cell_above(self):
        tables = _only_sheet(self._far_labels([[None], ["Fees"], ["Travel"], ["Total"]])).tables

        assert [(table.range.ref, table.label_column) for table in tables] == [("B1:J4", 2)]

    def test_far_labels_not_aligned_row_for_row_stay_apart(self):
        tables = _only_sheet(self._far_labels([["Unit"], ["Fees"], [None], ["Travel"], ["Total"]])).tables

        assert all(table.range.min_col == table.range.max_col or table.range.min_col == 8 for table in tables)

    def test_far_text_column_beside_a_text_column_stays_apart(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Owner"], ["Ann"], ["Bob"], ["Cid"]])
        _write(sheet, 1, 7, [["City"], ["Lyon"], ["Nice"], ["Metz"]])

        sheet_tables = _only_sheet(workbook)

        # Two lone columns of text: notes, never one table named by the other
        assert sheet_tables.tables == []
        assert sheet_tables.notes_total == 8

    def test_side_by_side_tables_each_keyed_by_dates_stay_apart(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Month", "Low", "High"]])
        _write(sheet, 1, 5, [["Month", "Units", "Value"]])
        for month in range(1, 7):
            day = datetime(2026, month, 1)
            _write(sheet, 1 + month, 1, [[day, month * 1.5, month * 2.5]])
            _write(sheet, 1 + month, 5, [[day, month * 3.0, month * 7.5]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:C7", "E1:G7"]

    def test_block_keyed_by_labels_beside_a_block_keyed_by_dates_stays_apart(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Month", "Units", "Value"]])
        _write(sheet, 1, 5, [["Product", "Units", "Value"]])
        for month in range(1, 7):
            _write(sheet, 1 + month, 1, [[datetime(2026, month, 1), month * 3.0, month * 7.5]])
            _write(sheet, 1 + month, 5, [[f"Product {month}", month * 1.5, month * 2.5]])

        tables = _only_sheet(workbook).tables

        assert [table.range.ref for table in tables] == ["A1:C7", "E1:G7"]

    @staticmethod
    def _two_columns(top: list, bold: bool) -> Workbook:
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [top, ["Sales", 10.5, 12.3], ["Costs", 4.2, 4.9], ["Rent", 1.5, 1.5],
                             ["Margin", 4.8, 5.9]])
        if bold:
            for col in range(1, 4):
                sheet.cell(row=1, column=col).font = BOLD
        return workbook

    def test_two_consecutive_years_in_bold_are_a_header(self):
        table = _only_sheet(self._two_columns(["Line", 2026, 2027], bold=True)).tables[0]

        assert table.header_rows == [1]
        assert table.nature is TableNature.TIME_SERIES

    def test_two_plain_consecutive_integers_are_not_told_from_a_row_of_figures(self):
        # Known limit: without formatting, "Line | 2026 | 2027" reads like "Total | 41 | 42"
        table = _only_sheet(self._two_columns(["Line", 2026, 2027], bold=False)).tables[0]

        assert table.header_rows == []

    def test_a_bold_first_row_of_two_figures_is_data(self):
        table = _only_sheet(self._two_columns(["Total", 10, 12], bold=True)).tables[0]

        assert table.header_rows == []

    def test_bold_year_row_over_linear_projections_is_a_header(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [["Budget", 2024, 2025, 2026, 2027], ["Ads", 100, 200, 300, 400],
                             ["Events", 50, 60, 70, 80], ["Total", 150, 260, 370, 480]])
        for col in range(1, 6):
            sheet.cell(row=1, column=col).font = BOLD

        table = _only_sheet(workbook).tables[0]

        assert table.header_rows == [1]
        assert table.nature is TableNature.TIME_SERIES


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: A pivot cache with a manually grouped field (fieldGroup/discretePr): openpyxl 3.1.5 fails to parse it
_PIVOT_CACHE = (
    f'<pivotCacheDefinition xmlns="{_MAIN_NS}" xmlns:r="{_REL_NS}" recordCount="0">'
    '<cacheSource type="worksheet"><worksheetSource ref="A3:C6" sheet="Data"/></cacheSource>'
    '<cacheFields count="1"><cacheField name="Product" numFmtId="0"><sharedItems/>'
    '<fieldGroup base="0"><discretePr count="2"><x v="0"/><x v="1"/></discretePr></fieldGroup>'
    "</cacheField></cacheFields></pivotCacheDefinition>"
)
_PIVOT_TABLE = (
    f'<pivotTableDefinition xmlns="{_MAIN_NS}" name="Pivot" cacheId="7" dataCaption="Values">'
    '<location ref="F3:G5" firstHeaderRow="1" firstDataRow="1" firstDataCol="1"/></pivotTableDefinition>'
)


def _with_pivot_table(content: bytes) -> bytes:
    """Add a pivot cache and a pivot table on the first sheet to an .xlsx written by openpyxl."""
    source = zipfile.ZipFile(io.BytesIO(content))
    output = io.BytesIO()
    with source, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info).decode()
            if info.filename == "[Content_Types].xml":
                data = data.replace("</Types>", (
                    '<Override PartName="/xl/pivotCache/pivotCacheDefinition1.xml" ContentType="application/'
                    'vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheDefinition+xml"/>'
                    '<Override PartName="/xl/pivotTables/pivotTable1.xml" ContentType="application/'
                    'vnd.openxmlformats-officedocument.spreadsheetml.pivotTable+xml"/></Types>'))
            elif info.filename == "xl/_rels/workbook.xml.rels":
                data = data.replace("</Relationships>", (
                    f'<Relationship Id="rIdPivot1" Type="{_REL_NS}/pivotCacheDefinition" '
                    'Target="pivotCache/pivotCacheDefinition1.xml"/></Relationships>'))
            elif info.filename == "xl/workbook.xml":
                data = data.replace("</workbook>", (
                    '<pivotCaches><pivotCache cacheId="7" r:id="rIdPivot1"/></pivotCaches></workbook>'))
            target.writestr(info, data)
        target.writestr("xl/pivotCache/pivotCacheDefinition1.xml", _PIVOT_CACHE)
        target.writestr("xl/pivotTables/pivotTable1.xml", _PIVOT_TABLE)
        target.writestr("xl/worksheets/_rels/sheet1.xml.rels", (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL_NS}/pivotTable" Target="../pivotTables/pivotTable1.xml"/>'
            "</Relationships>"))
    return output.getvalue()


def _titled_workbook() -> Workbook:
    workbook = Workbook()
    sheet = _sheet(workbook, "Data")
    _write(sheet, 1, 1, [["Stock by product"]])
    sheet.merge_cells("A1:E1")
    _write(sheet, 3, 1, [["Product", "Units", "Value"], ["Alpha", 3, 30.0], ["Beta", 4, 52.5], ["Gamma", 1, 9.9]])
    return workbook


class TestOpening:
    def test_workbook_with_a_pivot_cache_openpyxl_cannot_parse_opens_in_normal_mode(self):
        content = _with_pivot_table(_to_bytes(_titled_workbook()))
        assert without_pivot_tables(content) is not None

        result = detect_tables(content)

        assert result.read_only is False
        table = result.tables[0]
        assert table.range.ref == "A3:C6"
        # The merged title is only recognised in normal mode: merged ranges were kept
        assert table.title == "Stock by product"

    def test_workbook_without_pivot_tables_is_left_alone(self):
        assert without_pivot_tables(_to_bytes(_titled_workbook())) is None
        assert without_pivot_tables(b"not a zip archive") is None

    def test_read_only_fallback_is_reported(self):
        real_load = loading.load_workbook

        def failing_in_normal_mode(*args, **kwargs):
            if not kwargs.get("read_only"):
                raise TypeError("parser failure")
            return real_load(*args, **kwargs)

        with patch.object(loading, "load_workbook", side_effect=failing_in_normal_mode):
            result = detect_tables(_to_bytes(_titled_workbook()))

        assert result.read_only is True
        assert result.sheets[0].read_only is True
        assert result.tables[0].range.ref == "A3:C6"

    def test_a_file_that_is_no_workbook_raises(self):
        with pytest.raises(zipfile.BadZipFile):
            detect_tables(b"not a zip archive")

    def test_a_damaged_archive_raises_the_error_of_the_first_attempt(self):
        content = bytearray(_with_pivot_table(_to_bytes(_titled_workbook())))
        with zipfile.ZipFile(io.BytesIO(bytes(content))) as archive:
            damaged = archive.getinfo("xl/worksheets/sheet1.xml")
        # Bytes of one member's compressed data overwritten: the archive opens, the member does not read
        start = damaged.header_offset + 30 + len(damaged.filename) + 10
        content[start:start + 8] = b"\x00" * 8
        with pytest.raises(Exception) as direct:
            load_workbook(io.BytesIO(bytes(content)), data_only=True)

        with pytest.raises(type(direct.value)):
            detect_tables(bytes(content))

    def test_a_workbook_part_named_alike_is_not_read_for_pivot_references(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("xl/myworkbook.xml", "<pivotCaches><pivotCache/></pivotCaches>")
        assert without_pivot_tables(buffer.getvalue()) is None

    def test_path_and_stream_sources(self, tmp_path):
        content = _to_bytes(_titled_workbook())
        path = tmp_path / "book.xlsx"
        path.write_bytes(content)

        assert detect_tables(path).tables[0].range.ref == "A3:C6"
        assert detect_tables(str(path)).tables[0].range.ref == "A3:C6"
        assert detect_tables(io.BytesIO(content)).tables[0].range.ref == "A3:C6"


class TestSequenceRuns:
    @pytest.mark.parametrize("values, expected", [
        ([2024, 2025, 2026], [(1, 3, SequenceKind.NUMBER)]),
        (["S1", "S2", "S3", "Total"], [(1, 3, SequenceKind.NUMBERED_TEXT)]),
        (["Week 1", "Week 2", "week 3"], [(1, 3, SequenceKind.NUMBERED_TEXT)]),
        ([datetime(2026, 1, 1), datetime(2026, 2, 1), datetime(2026, 3, 1)], [(1, 3, SequenceKind.DATE)]),
        ([1, 2, 4], []),
        ([3, 3, 3], []),
        (["S1", "T2", "S3"], []),
        ([2024, 2025], []),
    ])
    def test_runs(self, values, expected):
        assert sequence_runs(list(enumerate(values, start=1))) == expected

    def test_two_values_count_only_when_asked_and_consecutive(self):
        assert sequence_runs([(1, 2026), (2, 2027)]) == []
        assert sequence_runs([(1, 2026), (2, 2027)], min_length=2) == [(1, 2, SequenceKind.NUMBER)]
        assert sequence_runs([(1, 10), (2, 12)], min_length=2) == []
        assert sequence_runs([(1, "Option 1"), (2, "Option 2")], min_length=2) == []
        assert sequence_runs([(1, datetime(2026, 1, 1)), (2, datetime(2026, 6, 1))], min_length=2) == [
            (1, 2, SequenceKind.DATE)]

    def test_a_gap_in_positions_ends_a_run(self):
        assert sequence_runs([(1, 2024), (2, 2025), (4, 2026), (5, 2027)]) == []


class TestReadingByCells:
    """What keeps the detection's cost on the number of values, not on the area or the height of a box."""

    def _grid(self) -> SheetGrid:
        values = {(row, 1): f"name {row}" for row in range(1, 11) if row != 4}
        values.update({(row, 3): row * 1.5 for row in (2, 3, 9)})
        values[(10, 3)] = "#DIV/0!"
        return SheetGrid(values, [])

    def test_the_first_and_the_last_rows_of_a_box_are_read_without_the_others(self):
        grid, box = self._grid(), Box(1, 1, 10, 3)
        rows = grid.content_rows(box)
        assert rows == [1, 2, 3, 5, 6, 7, 8, 9, 10]
        assert grid.content_rows(box, limit=4) == rows[:4]
        assert grid.content_rows(box, limit=50) == rows
        assert grid.last_content_rows(box, 4) == rows[-4:]
        assert grid.last_content_rows(box, 50) == rows

    def test_columns_are_counted_by_their_cells_as_one_by_one(self):
        grid, rows = self._grid(), list(range(1, 11))
        counts = column_kind_counts(grid, rows, 1, 3)
        assert set(counts) == {1, 3}
        assert counts[3] == {Kind.NUMBER: 3, Kind.ERROR: 1}
        for col in (1, 2, 3):
            assert dominant_of(counts.get(col, {}), 0.6) == dominant_kind(grid, col, rows, 0.6)
        # Errors are counted as values of the column, never as its type
        assert dominant_of({Kind.ERROR: 2}, 0.6) == (None, 0)

    def test_a_long_column_under_a_wide_header_is_described_by_its_cells(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        _write(sheet, 1, 1, [[f"h{col}" for col in range(1, 41)]])
        _write(sheet, 2, 1, [[row] for row in range(1, 400)])
        table = _only_sheet(workbook).tables[0]
        assert table.range.ref == "A1:AN400" and table.data_row_count == 399
        assert table.columns[0].dtype is CellType.NUMBER and table.columns[0].non_empty_count == 399
        assert all(column.dtype is CellType.EMPTY for column in table.columns[1:])

    def test_a_header_repeated_page_after_page_cuts_a_table_at_each(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        page = [["Name", "Amount", "Count"]] + [[f"n{row}", row * 1.5, row] for row in range(1, 25)]
        for number in range(6):
            _write(sheet, 1 + number * 25, 1, page)
        tables = _only_sheet(workbook).tables
        assert [table.range.ref for table in tables] == [
            f"A{1 + number * 25}:C{25 + number * 25}" for number in range(6)]
        assert all(table.data_row_count == 24 and len(table.header_rows) == 1 for table in tables)

    def test_notes_are_counted_past_the_ones_returned(self):
        workbook = Workbook()
        sheet = _sheet(workbook)
        for position in range(12):
            sheet.cell(row=1 + 5 * position, column=1 + 6 * (position % 3), value=f"note {position}")
        result = detect_tables(_to_bytes(workbook), options=DetectionOptions(max_notes=5)).sheets[0]
        assert len(result.notes) == 5 and result.notes_total == 12
