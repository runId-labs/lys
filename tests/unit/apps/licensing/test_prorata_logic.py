"""
Unit tests for prorata calculation logic (pure functions, no mocks).
"""
from datetime import datetime, timezone

from lys.apps.licensing.modules.subscription.prorata import (
    calculate_prorata,
    calculate_period_end,
    is_upgrade,
    is_downgrade,
)


class TestCalculateProrata:
    """Tests for calculate_prorata()."""

    def test_upgrade_positive_prorata(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, tzinfo=timezone.utc)
        change = datetime(2024, 1, 16, tzinfo=timezone.utc)
        # 31 total days, 16 remaining days
        # old daily = 1000/31 ≈ 32.26, new daily = 2000/31 ≈ 64.52
        # prorata = (64.52 - 32.26) * 16 ≈ 516
        result = calculate_prorata(1000, 2000, start, end, change)
        assert result > 0
        assert result == int((2000 / 31 - 1000 / 31) * 16)

    def test_downgrade_returns_zero(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, tzinfo=timezone.utc)
        change = datetime(2024, 1, 16, tzinfo=timezone.utc)
        result = calculate_prorata(2000, 1000, start, end, change)
        assert result == 0

    def test_no_remaining_days_returns_zero(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, tzinfo=timezone.utc)
        change = datetime(2024, 2, 1, tzinfo=timezone.utc)
        result = calculate_prorata(1000, 2000, start, end, change)
        assert result == 0

    def test_same_price_returns_zero(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, tzinfo=timezone.utc)
        change = datetime(2024, 1, 16, tzinfo=timezone.utc)
        result = calculate_prorata(1000, 1000, start, end, change)
        assert result == 0

    def test_handles_naive_datetimes(self):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 2, 1)
        change = datetime(2024, 1, 16)
        result = calculate_prorata(1000, 2000, start, end, change)
        assert result > 0

    def test_change_after_end_returns_zero(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 2, 1, tzinfo=timezone.utc)
        change = datetime(2024, 2, 5, tzinfo=timezone.utc)
        result = calculate_prorata(1000, 2000, start, end, change)
        assert result == 0


class TestIsUpgradeDowngrade:
    """Tests for is_upgrade() and is_downgrade()."""

    def test_is_upgrade_higher_price(self):
        assert is_upgrade(1000, 2000) is True

    def test_is_upgrade_lower_price(self):
        assert is_upgrade(2000, 1000) is False

    def test_is_upgrade_same_price(self):
        assert is_upgrade(1000, 1000) is False

    def test_is_downgrade_lower_price(self):
        assert is_downgrade(2000, 1000) is True

    def test_is_downgrade_higher_price(self):
        assert is_downgrade(1000, 2000) is False

    def test_is_downgrade_same_price(self):
        assert is_downgrade(1000, 1000) is False


class TestCalculatePeriodEnd:
    """Tests for calculate_period_end()."""

    def test_monthly_normal(self):
        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "monthly")
        assert end.month == 2
        assert end.day == 15
        assert end.year == 2024

    def test_monthly_december_wraps_to_january(self):
        start = datetime(2024, 12, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "monthly")
        assert end.month == 1
        assert end.year == 2025

    def test_monthly_jan31_to_feb28(self):
        start = datetime(2024, 1, 31, tzinfo=timezone.utc)
        end = calculate_period_end(start, "monthly")
        assert end.month == 2
        assert end.day == 29  # 2024 is a leap year

    def test_yearly_normal(self):
        start = datetime(2024, 3, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "yearly")
        assert end.year == 2025
        assert end.month == 3
        assert end.day == 15

    def test_yearly_feb29_to_feb28(self):
        start = datetime(2024, 2, 29, tzinfo=timezone.utc)
        end = calculate_period_end(start, "yearly")
        assert end.year == 2025
        assert end.month == 2
        assert end.day == 28
