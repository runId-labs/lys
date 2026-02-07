"""
Unit tests for user_auth event webservices.

Tests structure of EventQuery, UserEventPreferenceQuery, and UserEventPreferenceMutation.

Note: Webservice modules use a singleton registry that can raise ValueError
when multiple apps register webservices with the same name.
"""

import inspect
import sys

_mod = None
_module_name = "lys.apps.user_auth.modules.event.webservices"
if _module_name in sys.modules:
    _mod = sys.modules[_module_name]
else:
    try:
        import importlib
        _mod = importlib.import_module(_module_name)
    except (ValueError, ImportError):
        _mod = None


def _get_mod():
    import pytest
    if _mod is None:
        pytest.skip("event webservices could not be imported due to registry conflict")
    return _mod


class TestEventQueryStructure:
    """Tests for EventQuery class."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "EventQuery")

    def test_has_configurable_events_method(self):
        mod = _get_mod()
        assert hasattr(mod.EventQuery, "configurable_events")


class TestUserEventPreferenceQueryStructure:
    """Tests for UserEventPreferenceQuery class."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "UserEventPreferenceQuery")

    def test_has_my_event_preferences_method(self):
        mod = _get_mod()
        assert hasattr(mod.UserEventPreferenceQuery, "my_event_preferences")


class TestUserEventPreferenceMutationStructure:
    """Tests for UserEventPreferenceMutation class."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "UserEventPreferenceMutation")

    def test_has_set_event_preference_method(self):
        mod = _get_mod()
        assert hasattr(mod.UserEventPreferenceMutation, "set_event_preference")
