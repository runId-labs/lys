"""
Unit tests for licensing tasks structure.

Tests that Celery tasks are properly defined.
"""

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.tasks import apply_pending_plan_changes


class TestApplyPendingPlanChangesTask:
    """Tests for apply_pending_plan_changes Celery task."""

    def test_function_exists(self):
        assert apply_pending_plan_changes is not None

    def test_is_callable(self):
        assert callable(apply_pending_plan_changes)

    def test_has_delay_attribute(self):
        """Celery shared_task decorator adds .delay method."""
        assert hasattr(apply_pending_plan_changes, "delay")

    def test_has_apply_async_attribute(self):
        """Celery shared_task decorator adds .apply_async method."""
        assert hasattr(apply_pending_plan_changes, "apply_async")

    def test_has_name_attribute(self):
        """Celery shared_task decorator adds .name attribute."""
        assert hasattr(apply_pending_plan_changes, "name")

    def test_name_contains_function_name(self):
        """Task name should contain the function name."""
        assert "apply_pending_plan_changes" in apply_pending_plan_changes.name
