"""
Whether the figures of an agent's analysis come from its run: each number it writes is looked for in
what the run read — the task, the tools' results, its calculate steps.

A model that reads well still writes figures it did not read: a total rounded from memory, a change
computed in its head, an amount carried over from a neighbouring line. Nothing in the text tells them
apart from a figure read. This check does: a figure found nowhere in the run is unsourced, and the
agent is sent back to take it from a reading, compute it with calculate, or remove it.

What it does not see: a figure that IS in the run but attached to the wrong thing (a December balance
called the year's low). That is a matter of meaning, for the caller's own check or for the reading
itself to state it.
"""

import bisect
import re
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, NamedTuple, Optional

from lys.apps.ai.utils.figures import MIN_SIGNIFICANT_DIGITS, rounding_tolerance, significant_digits

#: How many unsourced figures one check reports: the agent corrects the first, the next round sees the rest
MAX_REPORTED = 15

#: Characters of text shown before and after a figure, for the agent to find it in its analysis
CONTEXT_CHARACTERS = 50

# A number as a text writes it: grouped thousands (space, no-break space, narrow no-break space) or not,
# a decimal part after a point or a comma, then an optional scale or unit
_NUMBER = re.compile(
    r"(?<![\w/.,])(?P<sign>[-−+])?(?P<int>\d{1,3}(?:[   ]\d{3})+|\d+)"
    r"(?:[.,](?P<dec>\d+))?(?![\w/])"
    r"(?:[   ]?(?P<unit>Md€|Mds?|M€|k€|K€|%|‰))?"
)

_SCALES = {"k€": Decimal(1_000), "K€": Decimal(1_000), "M€": Decimal(1_000_000),
           "Md€": Decimal(1_000_000_000), "Md": Decimal(1_000_000_000), "Mds": Decimal(1_000_000_000)}


class CitedFigure(NamedTuple):
    """A number an analysis writes: its value in units, the rounding its digits allow, and where it is."""

    value: Decimal
    tolerance: Decimal
    percent: bool
    text: str
    start: int


def unsourced_figures(analysis: str, sources: Iterable[str]) -> List[CitedFigure]:
    """
    The figures of ``analysis`` found in none of ``sources``, in text order, at most MAX_REPORTED.

    A figure is found when a number of the sources equals it within the rounding its written digits
    allow (750 k€ is 750 000 within 500), at the scale it is written in; a percentage is also found as
    the ratio a calculation returns (15,9 % against 0.159). Years, dates and numbers too short to tell
    are not checked.
    """
    known = sorted({abs(number) for source in sources for number in _source_numbers(source)})
    missing = []
    for figure in _cited(analysis):
        if not _found(figure, known):
            missing.append(figure)
            if len(missing) >= MAX_REPORTED:
                break
    return missing


def context_of(analysis: str, figure: CitedFigure) -> str:
    """The figure with the text around it, on one line: where the agent finds it in its analysis."""
    start = max(0, figure.start - CONTEXT_CHARACTERS)
    end = min(len(analysis), figure.start + len(figure.text) + CONTEXT_CHARACTERS)
    return " ".join(analysis[start:end].split())


def _cited(text: str) -> Iterable[CitedFigure]:
    for match in _NUMBER.finditer(text):
        unit = match.group("unit")
        value = _decimal(match)
        if value is None or significant_digits(value) < MIN_SIGNIFICANT_DIGITS or _is_year(match, unit):
            continue
        decimals = len(match.group("dec") or "")
        scale = _SCALES.get(unit or "", Decimal(1))
        tolerance = rounding_tolerance(decimals, scale)
        yield CitedFigure(abs(value) * scale, tolerance, unit in ("%", "‰"), match.group(0), match.start())


def _source_numbers(text: str) -> Iterable[Decimal]:
    for match in _NUMBER.finditer(text):
        value = _decimal(match)
        if value is not None:
            yield value * _SCALES.get(match.group("unit") or "", Decimal(1))
    # A plain number the grouped pattern reads as two (a JSON value next to a word, an exponent) is
    # read again as it stands
    for raw in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text):
        try:
            yield Decimal(raw)
        except InvalidOperation:
            continue


def _found(figure: CitedFigure, known: List[Decimal]) -> bool:
    targets = [(figure.value, figure.tolerance)]
    if figure.percent:
        # A percentage written from a ratio a calculation returned (15,9 % from 0.159)
        targets.append((figure.value / 100, figure.tolerance / 100))
    for target, tolerance in targets:
        index = bisect.bisect_left(known, target - tolerance)
        if index < len(known) and known[index] <= target + tolerance:
            return True
    return False


def _is_year(match: re.Match, unit: Optional[str]) -> bool:
    """A year (2026) or a fiscal year written alone: a label, not a figure."""
    raw = match.group("int")
    return unit is None and match.group("dec") is None and raw.isdigit() and len(raw) == 4 \
        and 1900 <= int(raw) <= 2100


def _decimal(match: re.Match) -> Optional[Decimal]:
    integer = re.sub(r"\D", "", match.group("int"))
    text = integer + (f".{match.group('dec')}" if match.group("dec") else "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if match.group("sign") in ("-", "−") else value
