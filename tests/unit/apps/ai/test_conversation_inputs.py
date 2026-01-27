"""
Unit tests for AI conversation GraphQL inputs.

Tests Strawberry input types.
"""

import pytest


class TestAIMessageInput:
    """Tests for AIMessageInput."""

    def test_input_exists(self):
        """Test AIMessageInput class exists."""
        from lys.apps.ai.modules.conversation.inputs import AIMessageInput
        assert AIMessageInput is not None

    def test_input_has_strawberry_definition(self):
        """Test AIMessageInput is a Strawberry input type."""
        from lys.apps.ai.modules.conversation.inputs import AIMessageInput
        assert hasattr(AIMessageInput, "__strawberry_definition__")

    def test_input_is_input_type(self):
        """Test AIMessageInput is a Strawberry input type."""
        from lys.apps.ai.modules.conversation.inputs import AIMessageInput
        definition = AIMessageInput.__strawberry_definition__
        assert definition.is_input is True

    def test_input_has_to_pydantic_method(self):
        """Test AIMessageInput can convert to Pydantic model."""
        from lys.apps.ai.modules.conversation.inputs import AIMessageInput
        assert hasattr(AIMessageInput, "to_pydantic")


class TestAIToolResult:
    """Tests for AIToolResult."""

    def test_type_exists(self):
        """Test AIToolResult class exists."""
        from lys.apps.ai.modules.conversation.inputs import AIToolResult
        assert AIToolResult is not None

    def test_type_has_strawberry_definition(self):
        """Test AIToolResult is a Strawberry type."""
        from lys.apps.ai.modules.conversation.inputs import AIToolResult
        assert hasattr(AIToolResult, "__strawberry_definition__")


class TestFrontendAction:
    """Tests for FrontendAction."""

    def test_type_exists(self):
        """Test FrontendAction class exists."""
        from lys.apps.ai.modules.conversation.inputs import FrontendAction
        assert FrontendAction is not None

    def test_type_has_strawberry_definition(self):
        """Test FrontendAction is a Strawberry type."""
        from lys.apps.ai.modules.conversation.inputs import FrontendAction
        assert hasattr(FrontendAction, "__strawberry_definition__")

    def test_type_has_type_field(self):
        """Test FrontendAction has type field."""
        from lys.apps.ai.modules.conversation.inputs import FrontendAction
        assert "type" in FrontendAction.__annotations__

    def test_type_has_path_field(self):
        """Test FrontendAction has path field."""
        from lys.apps.ai.modules.conversation.inputs import FrontendAction
        assert "path" in FrontendAction.__annotations__

    def test_type_has_params_field(self):
        """Test FrontendAction has params field."""
        from lys.apps.ai.modules.conversation.inputs import FrontendAction
        assert "params" in FrontendAction.__annotations__

    def test_type_has_nodes_field(self):
        """Test FrontendAction has nodes field."""
        from lys.apps.ai.modules.conversation.inputs import FrontendAction
        assert "nodes" in FrontendAction.__annotations__
