"""
Unit tests for core utils datetime module.

Tests datetime utility functions.
"""

import pytest
from datetime import datetime, timezone


class TestNowUtc:
    """Tests for now_utc function."""

    def test_function_exists(self):
        """Test now_utc function exists."""
        from lys.core.utils.datetime import now_utc
        assert now_utc is not None
        assert callable(now_utc)

    def test_returns_datetime(self):
        """Test now_utc returns a datetime object."""
        from lys.core.utils.datetime import now_utc
        result = now_utc()
        assert isinstance(result, datetime)

    def test_returns_timezone_aware(self):
        """Test now_utc returns timezone-aware datetime."""
        from lys.core.utils.datetime import now_utc
        result = now_utc()
        assert result.tzinfo is not None

    def test_returns_utc_timezone(self):
        """Test now_utc returns UTC timezone."""
        from lys.core.utils.datetime import now_utc
        result = now_utc()
        assert result.tzinfo == timezone.utc

    def test_returns_current_time(self):
        """Test now_utc returns approximately current time."""
        from lys.core.utils.datetime import now_utc
        before = datetime.now(timezone.utc)
        result = now_utc()
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_consecutive_calls_increase(self):
        """Test consecutive calls return increasing times."""
        from lys.core.utils.datetime import now_utc
        import time
        first = now_utc()
        time.sleep(0.01)  # 10ms
        second = now_utc()
        assert second > first
