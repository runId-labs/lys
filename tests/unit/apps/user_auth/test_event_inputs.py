"""
Unit tests for user_auth event inputs.

Tests Strawberry GraphQL input types for event preferences.
"""

from lys.apps.user_auth.modules.event.inputs import SetEventPreferenceInput


class TestSetEventPreferenceInputStructure:
    """Tests for SetEventPreferenceInput class."""

    def test_class_exists(self):
        assert SetEventPreferenceInput is not None

    def test_has_to_pydantic_method(self):
        """Strawberry pydantic input classes have to_pydantic method."""
        assert hasattr(SetEventPreferenceInput, "to_pydantic")

    def test_has_event_type_field(self):
        annotations = getattr(SetEventPreferenceInput, "__annotations__", {})
        assert "event_type" in annotations

    def test_has_channel_field(self):
        annotations = getattr(SetEventPreferenceInput, "__annotations__", {})
        assert "channel" in annotations

    def test_has_enabled_field(self):
        annotations = getattr(SetEventPreferenceInput, "__annotations__", {})
        assert "enabled" in annotations
