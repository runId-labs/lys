"""
Unit tests for AI conversation GraphQL webservices.

Tests mutation structure.
"""

import pytest
import inspect


class TestAIMutation:
    """Tests for AIMutation."""

    def test_mutation_exists(self):
        """Test AIMutation class exists."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation
        assert AIMutation is not None

    def test_mutation_inherits_from_mutation(self):
        """Test AIMutation inherits from Mutation."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation
        from lys.core.graphql.types import Mutation
        assert issubclass(AIMutation, Mutation)

    def test_mutation_has_strawberry_type_decorator(self):
        """Test AIMutation is decorated with strawberry.type."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation
        assert hasattr(AIMutation, "__strawberry_definition__")

    def test_send_ai_message_method_exists(self):
        """Test send_ai_message method exists."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation
        assert hasattr(AIMutation, "send_ai_message")

    def test_send_ai_message_is_async(self):
        """Test send_ai_message is async."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation
        assert inspect.iscoroutinefunction(AIMutation.send_ai_message)

    def test_send_ai_message_signature(self):
        """Test send_ai_message method signature."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation

        sig = inspect.signature(AIMutation.send_ai_message)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "inputs" in params
        assert "info" in params

    def test_send_ai_message_returns_ai_message_node(self):
        """Test send_ai_message returns AIMessageNode."""
        from lys.apps.ai.modules.conversation.webservices import AIMutation

        sig = inspect.signature(AIMutation.send_ai_message)
        assert "AIMessageNode" in str(sig.return_annotation)
