"""
Opening a workbook for detection, robustly.

Normal mode is wanted (merged ranges, fonts and native tables are only loaded there), but it parses parts
the detector never reads, and openpyxl fails on some of them. Observed with openpyxl 3.1.5: a pivot cache
holding a manually grouped field (``fieldGroup/discretePr``) raises a TypeError, and openpyxl reads the
pivot caches for every worksheet, so the whole workbook fails to open.

Three attempts, in order:
1. normal mode, as the file is;
2. if the workbook declares pivot tables: normal mode on an in-memory copy whose pivot references are
   removed (``<pivotCaches>`` in the workbook part, pivotTable relationships of the sheets). A pivot
   table's displayed values are stored in its sheet's cells, so nothing the detector reads is lost;
3. read-only mode, which skips those parts but loads no merged ranges, fonts nor native tables: the
   result carries ``read_only=True``.
When every attempt fails, the error of the first one is raised.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import Any, Optional

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

#: The workbook part's list of pivot caches (any namespace prefix, with children or self-closing)
_PIVOT_CACHES = re.compile(
    rb"<(?:[\w.-]+:)?pivotCaches\b[^>]*/>|<((?:[\w.-]+:)?)pivotCaches\b.*?</\1pivotCaches>", re.DOTALL)

#: A relationship from a sheet to a pivot table (transitional and strict OOXML type URIs end alike)
_PIVOT_TABLE_RELATIONSHIP = re.compile(rb"<Relationship\b[^>]*?Type=\"[^\"]*/pivotTable\"[^>]*/>")


def open_workbook(content: bytes) -> Any:
    """
    An openpyxl workbook opened with its saved values (``data_only``), in normal mode when openpyxl can.

    Raises:
        The exception of the normal-mode attempt when no attempt opens the file (not a workbook)
    """
    try:
        return load_workbook(io.BytesIO(content), data_only=True)
    except Exception as first_error:  # noqa: BLE001 — openpyxl parser bugs raise arbitrary types
        try:
            stripped = without_pivot_tables(content)
        except Exception as error:  # noqa: BLE001 — a damaged archive member: no copy, the next attempt decides
            logger.warning("Workbook could not be copied without its pivot tables (%s)", type(error).__name__)
            stripped = None
        if stripped is not None:
            try:
                workbook = load_workbook(io.BytesIO(stripped), data_only=True)
            except Exception as error:  # noqa: BLE001
                logger.warning("Workbook does not open without its pivot tables either (%s)", type(error).__name__)
            else:
                logger.info("Workbook opened without its pivot tables (%s)", type(first_error).__name__)
                return workbook
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:  # noqa: BLE001
            raise first_error from None
        logger.warning(
            "Workbook opened read-only after a normal-mode failure (%s): merged ranges, fonts and native "
            "tables are not available", type(first_error).__name__,
        )
        return workbook


def without_pivot_tables(content: bytes) -> Optional[bytes]:
    """
    A copy of an .xlsx archive with its pivot references removed, or None when it declares none
    (or is not a zip archive).

    The archive is copied only once a reference was found: the parts that may hold one (the workbook
    part, the sheets' relationships) are read first, and a workbook without pivot tables costs no copy.

    Raises:
        What ``zipfile`` raises on a damaged member (``zipfile.BadZipFile``, ``zlib.error``...).
    """
    try:
        source = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        return None
    with source:
        rewritten: dict[str, bytes] = {}
        for info in source.infolist():
            pattern = _pivot_pattern(info.filename)
            if pattern is None:
                continue
            data, count = pattern.subn(b"", source.read(info))
            if count:
                rewritten[info.filename] = data
        if not rewritten:
            return None
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = rewritten[info.filename] if info.filename in rewritten else source.read(info)
                target.writestr(info, data)
    return output.getvalue()


def _pivot_pattern(part_name: str) -> Optional[re.Pattern[bytes]]:
    """The pivot references a part of the archive may hold, by its name; None for a part that holds none."""
    name = part_name.lower()
    if name.rsplit("/", 1)[-1] == "workbook.xml":
        return _PIVOT_CACHES
    if name.endswith(".rels") and "/worksheets/" in name:
        return _PIVOT_TABLE_RELATIONSHIP
    return None
