"""
Discount arithmetic.

Kept as pure functions: applying a discount is a computation on integers, it
needs no session and no entity, and both the subscription service and any
caller wanting to display a price before subscribing must obtain the same
result.
"""

from lys.apps.licensing.consts import PERCENT_UNIT


def discounted_amount(amount: int, value: int, unit_id: str) -> int:
    """Apply a discount to an amount expressed in currency minor units.

    The reduction is floored, so a fraction of a cent is never given away: on
    7 900,00 € at 30 % nothing is lost, on 9,99 € the client pays 7,00 € rather
    than 6,99 €. The rule matters less than its determinism — the same price and
    the same discount always produce the same amount, whatever computed it.

    Args:
        amount: Amount before discount, in currency minor units
        value: Discount value, read in its unit
        unit_id: Unit the value is expressed in

    Returns:
        The amount actually owed, never below zero.

    Raises:
        ValueError: If the unit is not one this function knows how to apply. A
            unit added to the reference data without being handled here would
            otherwise silently charge the full price.
    """
    if unit_id != PERCENT_UNIT:
        raise ValueError(f"Unsupported discount unit '{unit_id}'")

    if value <= 0:
        return amount

    capped = min(value, 100)

    return max(0, amount - (amount * capped) // 100)
