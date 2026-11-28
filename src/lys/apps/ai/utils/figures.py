"""
Reading a number the way it was written: what the checks of figures share
(``provenance``: where a number of a formula comes from; ``sourced_figures``: whether a figure of an
analysis was read in its run).
"""

from decimal import Decimal

#: Significant digits a number needs to be told apart: a count of months, a short rate or an ordinal
#: (12, 0.05, 3) match too many figures by chance to say where they come from
MIN_SIGNIFICANT_DIGITS = 3


def significant_digits(value: Decimal) -> int:
    """The digits of a number as written (4600 has four: an amount in thousands, not 46 hundreds)."""
    digits = value.as_tuple().digits
    return len(digits) - next((index for index, digit in enumerate(digits) if digit), len(digits))


def rounding_tolerance(decimals: int, scale: Decimal = Decimal(1)) -> Decimal:
    """
    How far a number written with ``decimals`` decimals, in units of ``scale``, may be from the value
    it rounds: half its last digit (750 k€ is 750 000 within 500).
    """
    return Decimal(5).scaleb(-decimals - 1) * scale
