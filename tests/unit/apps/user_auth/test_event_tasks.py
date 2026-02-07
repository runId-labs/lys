"""
Unit tests for user_auth event tasks.
"""


class TestTriggerEventTask:
    """Tests for trigger_event Celery task."""

    def test_task_exists(self):
        from lys.apps.user_auth.modules.event.tasks import trigger_event
        assert trigger_event is not None

    def test_task_is_callable(self):
        from lys.apps.user_auth.modules.event.tasks import trigger_event
        assert callable(trigger_event)

    def test_task_has_delay_attribute(self):
        """Celery tasks should have a .delay method."""
        from lys.apps.user_auth.modules.event.tasks import trigger_event
        assert hasattr(trigger_event, "delay")
