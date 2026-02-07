"""
Prorata calculation utilities for subscription billing.

Provides functions to calculate prorated amounts for:
- Upgrades: Immediate billing for the price difference
- Downgrades: No prorata (keeps access until period end)
"""

from datetime import datetime, timezone


def calculate_prorata(
    old_price: int,
    new_price: int,
    current_period_start: datetime,
    current_period_end: datetime,
    change_date: datetime | None = None
) -> int:
    """
    Calculate prorated amount for an upgrade.

    The prorata is calculated as:
    (new_daily_rate - old_daily_rate) * remaining_days

    Args:
        old_price: Current plan price in cents
        new_price: New plan price in cents
        current_period_start: Start of current billing period
        current_period_end: End of current billing period
        change_date: Date of plan change (defaults to now)

    Returns:
        Amount to charge in cents (0 if downgrade or no remaining days)
    """
    if change_date is None:
        change_date = datetime.now(timezone.utc)

    # Ensure timezone-aware datetimes
    if current_period_start.tzinfo is None:
        current_period_start = current_period_start.replace(tzinfo=timezone.utc)
    if current_period_end.tzinfo is None:
        current_period_end = current_period_end.replace(tzinfo=timezone.utc)
    if change_date.tzinfo is None:
        change_date = change_date.replace(tzinfo=timezone.utc)

    # Calculate days
    total_days = (current_period_end - current_period_start).days
    remaining_days = (current_period_end - change_date).days

    # No prorata if no remaining days or invalid period
    if remaining_days <= 0 or total_days <= 0:
        return 0

    # Calculate daily rates
    daily_old = old_price / total_days
    daily_new = new_price / total_days

    # Calculate prorata amount
    prorata_amount = (daily_new - daily_old) * remaining_days

    # Return 0 for downgrades (negative prorata)
    return max(0, int(prorata_amount))


def calculate_period_end(
    period_start: datetime,
    billing_period: str
) -> datetime:
    """
    Calculate the end of a billing period.

    Args:
        period_start: Start of the billing period
        billing_period: "monthly" or "yearly"

    Returns:
        End of the billing period (same day next month/year)
    """
    if billing_period == "yearly":
        # Add 1 year
        try:
            return period_start.replace(year=period_start.year + 1)
        except ValueError:
            # Handle Feb 29 -> Feb 28
            return period_start.replace(year=period_start.year + 1, day=28)
    else:
        # Add 1 month (default to monthly)
        month = period_start.month + 1
        year = period_start.year
        if month > 12:
            month = 1
            year += 1
        try:
            return period_start.replace(year=year, month=month)
        except ValueError:
            # Handle day overflow (e.g., Jan 31 -> Feb 28)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            return period_start.replace(year=year, month=month, day=last_day)


def is_upgrade(old_price: int, new_price: int) -> bool:
    """
    Determine if a plan change is an upgrade.

    Args:
        old_price: Current plan price in cents
        new_price: New plan price in cents

    Returns:
        True if new plan is more expensive (upgrade)
    """
    return new_price > old_price


def is_downgrade(old_price: int, new_price: int) -> bool:
    """
    Determine if a plan change is a downgrade.

    Args:
        old_price: Current plan price in cents
        new_price: New plan price in cents

    Returns:
        True if new plan is less expensive (downgrade)
    """
    return new_price < old_price