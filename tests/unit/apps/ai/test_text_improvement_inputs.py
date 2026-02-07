"""
Unit tests for AI text improvement inputs.

Tests Strawberry GraphQL input type for text improvement.
"""

from lys.apps.ai.modules.text_improvement.inputs import ImproveTextInput


class TestImproveTextInputStructure:
    """Tests for ImproveTextInput class."""

    def test_class_exists(self):
        assert ImproveTextInput is not None

    def test_has_to_pydantic_method(self):
        assert hasattr(ImproveTextInput, "to_pydantic")

    def test_has_text_field(self):
        annotations = getattr(ImproveTextInput, "__annotations__", {})
        assert "text" in annotations

    def test_has_context_field(self):
        annotations = getattr(ImproveTextInput, "__annotations__", {})
        assert "context" in annotations

    def test_has_language_field(self):
        annotations = getattr(ImproveTextInput, "__annotations__", {})
        assert "language" in annotations

    def test_has_max_length_field(self):
        annotations = getattr(ImproveTextInput, "__annotations__", {})
        assert "max_length" in annotations
