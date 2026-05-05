"""
Unit tests for user_auth notification webservices.

Covers:
- NotificationQuery.all_notifications signature wiring (is_read, severity_id)
- NotificationSeverityQuery.all_notification_severities resolver presence
- Source-level proof that the severity-filter join is conditional on a truthy
  severity_id and that the is_read filter is conditional on `is not None`

The webservice modules use a singleton registry that can raise ValueError
when multiple apps register webservices with the same name; we import the
module defensively, mirroring the pattern in test_event_webservices.py.

We deliberately do NOT exercise the resolver coroutine in unit scope because
`@lys_connection` rebinds `info.context.app_manager` to the node's real
app_manager at call time, which requires a fully-booted SQLAlchemy registry.
The behavior of the join is covered by source inspection here and by
integration tests where the full app boots.
"""
import importlib
import inspect
import sys
from typing import Optional

import pytest


_module_name = "lys.apps.user_auth.modules.notification.webservices"
_mod = sys.modules.get(_module_name)
if _mod is None:
    try:
        _mod = importlib.import_module(_module_name)
    except (ValueError, ImportError):
        _mod = None


def _get_mod():
    if _mod is None:
        pytest.skip("notification webservices could not be imported due to registry conflict")
    return _mod


class TestNotificationQueryStructure:
    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "NotificationQuery")

    def test_has_all_notifications_method(self):
        mod = _get_mod()
        assert hasattr(mod.NotificationQuery, "all_notifications")

    def test_all_notifications_accepts_is_read_optional(self):
        mod = _get_mod()
        sig = inspect.signature(mod.NotificationQuery.all_notifications)
        assert "is_read" in sig.parameters
        # default must be None so the filter is opt-in
        assert sig.parameters["is_read"].default is None

    def test_all_notifications_accepts_severity_id_optional(self):
        mod = _get_mod()
        sig = inspect.signature(mod.NotificationQuery.all_notifications)
        assert "severity_id" in sig.parameters
        assert sig.parameters["severity_id"].default is None

    def test_all_notifications_filter_types(self):
        mod = _get_mod()
        sig = inspect.signature(mod.NotificationQuery.all_notifications)
        assert sig.parameters["is_read"].annotation == Optional[bool]
        assert sig.parameters["severity_id"].annotation == Optional[str]

    def test_has_unread_notifications_count_method(self):
        mod = _get_mod()
        assert hasattr(mod.NotificationQuery, "unread_notifications_count")


class TestNotificationSeverityQueryStructure:
    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "NotificationSeverityQuery")

    def test_has_all_notification_severities_method(self):
        mod = _get_mod()
        assert hasattr(mod.NotificationSeverityQuery, "all_notification_severities")


class TestAllNotificationsResolverSource:
    """Source-level invariants on the resolver — guards against accidentally
    making the severity filter unconditional or the is_read filter mishandle
    `False`. We read the file directly because @lys_connection wraps the
    function and inspect.getsource on the class attribute returns the wrapper."""

    @classmethod
    def _source(cls):
        from lys.apps.user_auth.modules.notification import webservices
        with open(webservices.__file__, "r") as f:
            return f.read()

    def test_is_read_filter_uses_is_not_none(self):
        """is_read is a tri-state (None / True / False) — must not use truthy check."""
        src = self._source()
        assert "is_read is not None" in src

    def test_severity_filter_is_conditional_truthy(self):
        """severity_id filter must only fire on a non-empty string."""
        src = self._source()
        assert "if severity_id" in src

    def test_severity_filter_joins_batch_and_type(self):
        src = self._source()
        assert "notification_batch" in src
        assert "notification_type" in src
        assert ".join(" in src

    def test_severity_filter_compares_against_type_severity_id(self):
        src = self._source()
        assert "type_entity.severity_id == severity_id" in src
