"""
Unit tests for prorata calculation utilities.
"""
from datetime import datetime, timezone


class TestCalculateProrata:
    """Tests for calculate_prorata function."""

    def test_basic_upgrade(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 1, 16, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=1000, new_price=2000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        # 16 remaining days out of 31 total
        # daily_old = 1000/31 ≈ 32.26, daily_new = 2000/31 ≈ 64.52
        # prorata = (64.52 - 32.26) * 16 ≈ 516
        assert result > 0
        assert isinstance(result, int)

    def test_downgrade_returns_zero(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 1, 16, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=2000, new_price=1000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result == 0

    def test_same_price_returns_zero(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 1, 16, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=1000, new_price=1000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result == 0

    def test_no_remaining_days_returns_zero(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 2, 1, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=1000, new_price=2000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result == 0

    def test_change_after_period_end_returns_zero(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 2, 15, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=1000, new_price=2000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result == 0

    def test_full_period_upgrade(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=1000, new_price=2000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        # Full period: (2000 - 1000) / 31 * 31 = 1000
        assert result == 1000

    def test_naive_datetimes_handled(self):
        """Test that naive (non-timezone-aware) datetimes are handled."""
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)
        change = datetime(2025, 1, 16)

        result = calculate_prorata(
            old_price=1000, new_price=2000,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result > 0

    def test_zero_prices(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 1, 16, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=0, new_price=0,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result == 0

    def test_free_to_paid_upgrade(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 1, tzinfo=timezone.utc)
        change = datetime(2025, 1, 1, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=0, new_price=1900,
            current_period_start=start, current_period_end=end,
            change_date=change
        )
        assert result == 1900

    def test_default_change_date_uses_now(self):
        """Test that change_date defaults to now when not provided."""
        from lys.apps.licensing.modules.subscription.prorata import calculate_prorata

        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 2, 1, tzinfo=timezone.utc)

        result = calculate_prorata(
            old_price=1000, new_price=2000,
            current_period_start=start, current_period_end=end,
        )
        # Period is in the past, so remaining_days <= 0
        assert result == 0


class TestCalculatePeriodEnd:
    """Tests for calculate_period_end function."""

    def test_monthly_period(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "monthly")
        assert end == datetime(2025, 2, 15, tzinfo=timezone.utc)

    def test_yearly_period(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "yearly")
        assert end == datetime(2026, 1, 15, tzinfo=timezone.utc)

    def test_monthly_december_to_january(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

        start = datetime(2025, 12, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "monthly")
        assert end == datetime(2026, 1, 15, tzinfo=timezone.utc)

    def test_monthly_jan31_to_feb28(self):
        """Test day overflow from Jan 31 to Feb 28."""
        from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

        start = datetime(2025, 1, 31, tzinfo=timezone.utc)
        end = calculate_period_end(start, "monthly")
        assert end.month == 2
        assert end.day == 28

    def test_yearly_leap_year_feb29(self):
        """Test Feb 29 in leap year to Feb 28 in non-leap year."""
        from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

        start = datetime(2024, 2, 29, tzinfo=timezone.utc)
        end = calculate_period_end(start, "yearly")
        assert end == datetime(2025, 2, 28, tzinfo=timezone.utc)

    def test_unknown_period_defaults_to_monthly(self):
        from lys.apps.licensing.modules.subscription.prorata import calculate_period_end

        start = datetime(2025, 1, 15, tzinfo=timezone.utc)
        end = calculate_period_end(start, "unknown")
        assert end == datetime(2025, 2, 15, tzinfo=timezone.utc)


class TestIsUpgrade:
    """Tests for is_upgrade function."""

    def test_upgrade_returns_true(self):
        from lys.apps.licensing.modules.subscription.prorata import is_upgrade
        assert is_upgrade(1000, 2000) is True

    def test_downgrade_returns_false(self):
        from lys.apps.licensing.modules.subscription.prorata import is_upgrade
        assert is_upgrade(2000, 1000) is False

    def test_same_price_returns_false(self):
        from lys.apps.licensing.modules.subscription.prorata import is_upgrade
        assert is_upgrade(1000, 1000) is False

    def test_free_to_paid_is_upgrade(self):
        from lys.apps.licensing.modules.subscription.prorata import is_upgrade
        assert is_upgrade(0, 1900) is True


class TestIsDowngrade:
    """Tests for is_downgrade function."""

    def test_downgrade_returns_true(self):
        from lys.apps.licensing.modules.subscription.prorata import is_downgrade
        assert is_downgrade(2000, 1000) is True

    def test_upgrade_returns_false(self):
        from lys.apps.licensing.modules.subscription.prorata import is_downgrade
        assert is_downgrade(1000, 2000) is False

    def test_same_price_returns_false(self):
        from lys.apps.licensing.modules.subscription.prorata import is_downgrade
        assert is_downgrade(1000, 1000) is False

    def test_paid_to_free_is_downgrade(self):
        from lys.apps.licensing.modules.subscription.prorata import is_downgrade
        assert is_downgrade(1900, 0) is True
