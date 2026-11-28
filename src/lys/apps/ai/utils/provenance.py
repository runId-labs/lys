"""
Where the figures a tool returns come from, so that ``calculate`` sees what a formula combines.

A model handed two figures computes with them whatever they measure. Two figures that are both
right can still give a wrong result: an amount read in one source minus a different amount read in
another is a number with no meaning, and nothing in the formula says so. The tool that shows the
figures knows what each one is and where it was read; this module carries that knowledge to the
calculation.

A tool states it under ``PROVENANCE_KEY`` in its result: one entry per figure it shows, with its
value as the text shows it, what it measures (``measure``, a stable key, and ``label``, words for the
model), where it was read (``source``) and its unit. The key never reaches the model nor the client
(``model_result``): it stays in the stored result, so a later turn still knows where an earlier
reading came from. A figure no tool states is unknown, and an unknown figure raises no alert.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

from lys.apps.ai.utils.figures import MIN_SIGNIFICANT_DIGITS, rounding_tolerance, significant_digits

#: The key of a tool result under which the tool states the provenance of its figures
PROVENANCE_KEY = "_provenance"

#: The field a webservice tool's node states it in (``figures_provenance``, a JSON list of
#: ``figure`` entries): the executor moves it under PROVENANCE_KEY (``from_webservice``)
PROVENANCE_FIELD = "figuresProvenance"

#: The scales a model writes an amount in besides units: thousands (5 550 for 5 549 832) and millions
SCALES = (Decimal(1), Decimal(1_000), Decimal(1_000_000))


@dataclass(frozen=True)
class Figure:
    """A figure a tool showed: its value, what it measures, where it was read, its unit."""

    value: Decimal
    measure: str
    label: str
    source: str
    unit: str


def figure(value: Any, measure: str, label: str, source: str, unit: str) -> Optional[Dict[str, Any]]:
    """
    One provenance entry, as a tool puts it in its result; None when the value is no number (a figure
    the tool shows as missing has no provenance to state). The value is the one the text shows.
    """
    number = _decimal(value)
    if number is None:
        return None
    return {"value": str(number), "measure": measure, "label": label, "source": source, "unit": unit}


def from_webservice(result: Any) -> Any:
    """
    A webservice tool's result with the provenance its node states (PROVENANCE_FIELD) moved under
    PROVENANCE_KEY, where a special tool's result carries it: from there the turn keeps it and the
    model never gets it. A result without that field is returned as it is.
    """
    if isinstance(result, dict) and PROVENANCE_FIELD in result:
        moved = {key: value for key, value in result.items() if key != PROVENANCE_FIELD}
        if result[PROVENANCE_FIELD]:
            moved[PROVENANCE_KEY] = result[PROVENANCE_FIELD]
        return moved
    return result


def model_result(result: Any) -> Any:
    """A tool result as the model and the client get it: without the provenance of its figures."""
    if isinstance(result, dict) and PROVENANCE_KEY in result:
        return {key: value for key, value in result.items() if key != PROVENANCE_KEY}
    return result


class Provenance:
    """The figures the tools of a conversation showed, to tell where a number of a formula comes from."""

    def __init__(self) -> None:
        self._figures: List[Figure] = []

    def add(self, result: Any) -> None:
        """Keep the figures a tool result states; a malformed entry is left out, never an error."""
        entries = result.get(PROVENANCE_KEY) if isinstance(result, dict) else None
        if not isinstance(entries, list):
            return
        for entry in entries:
            parsed = _figure(entry)
            if parsed is not None:
                self._figures.append(parsed)

    def figure_of(self, literal: Decimal, decimals: int) -> Optional[Figure]:
        """
        The figure a number of a formula is, as the model wrote it: equal to a figure shown, or to it
        written in thousands or millions, within the rounding of the digits written. None when the
        number is too short to tell, matches no figure, or matches figures that do not agree on what
        they are (the same value shown for two measures or two sources).
        """
        if literal.is_zero() or significant_digits(literal) < MIN_SIGNIFICANT_DIGITS:
            return None
        matches = []
        for scale in SCALES:
            tolerance = rounding_tolerance(decimals, scale)
            value = literal * scale
            matches += [item for item in self._figures if abs(item.value - value) <= tolerance]
        kinds = {(item.measure, item.source, item.unit) for item in matches}
        return matches[0] if len(kinds) == 1 else None


def mixed_bases(left: Iterable[Figure], right: Iterable[Figure]) -> Optional[tuple]:
    """
    Two figures an operation sets against each other although they are not on the same basis: in the
    same unit, of different measures, read in different sources. The same measure in two sources is
    a gap (the actual against the budget); two measures of one source are its own arithmetic (revenue
    less expenses); a count against an amount is a ratio per head. None when nothing is mixed.
    """
    for one in left:
        for other in right:
            if one.unit == other.unit and one.measure != other.measure and one.source != other.source:
                return one, other
    return None


def _figure(entry: Any) -> Optional[Figure]:
    if not isinstance(entry, dict):
        return None
    value = _decimal(entry.get("value"))
    fields = [entry.get(name) for name in ("measure", "label", "source", "unit")]
    if value is None or not all(isinstance(field, str) and field for field in fields):
        return None
    return Figure(value, *fields)


def _decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None
