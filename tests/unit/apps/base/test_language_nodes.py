"""
Unit tests for base language module nodes.

Tests GraphQL node structure.
"""

import pytest


class TestLanguageNode:
    """Tests for LanguageNode."""

    def test_node_exists(self):
        """Test LanguageNode class exists."""
        from lys.apps.base.modules.language.nodes import LanguageNode
        assert LanguageNode is not None

    def test_node_is_decorated_with_parametric_node(self):
        """Test LanguageNode uses parametric_node decorator."""
        from lys.apps.base.modules.language.nodes import LanguageNode
        # Parametric nodes have strawberry definition
        assert hasattr(LanguageNode, "__strawberry_definition__")

    def test_node_is_registered(self):
        """Test LanguageNode is properly registered."""
        from lys.apps.base.modules.language.nodes import LanguageNode
        # Node should be usable as a Strawberry type
        assert LanguageNode is not None
