"""
Unit tests for licensing Celery tasks.
"""
import inspect


class TestApplyPendingPlanChangesTask:
    """Tests for apply_pending_plan_changes Celery task."""

    def test_task_exists(self):
        from lys.apps.licensing.tasks import apply_pending_plan_changes
        assert apply_pending_plan_changes is not None

    def test_task_is_callable(self):
        from lys.apps.licensing.tasks import apply_pending_plan_changes
        assert callable(apply_pending_plan_changes)

    def test_task_has_celery_attributes(self):
        """Celery tasks should have a .delay attribute."""
        from lys.apps.licensing.tasks import apply_pending_plan_changes
        assert hasattr(apply_pending_plan_changes, "delay")
