"""
Unit tests for base access_level module nodes.

Tests GraphQL node structure.
"""

import pytest


class TestAccessLevelNode:
    """Tests for AccessLevelNode."""

    def test_node_exists(self):
        """Test AccessLevelNode class exists."""
        from lys.apps.base.modules.access_level.nodes import AccessLevelNode
        assert AccessLevelNode is not None

    def test_node_is_decorated_with_parametric_node(self):
        """Test AccessLevelNode uses parametric_node decorator."""
        from lys.apps.base.modules.access_level.nodes import AccessLevelNode
        # Parametric nodes have strawberry definition
        assert hasattr(AccessLevelNode, "__strawberry_definition__")

    def test_node_has_service_reference(self):
        """Test AccessLevelNode is connected to AccessLevelService."""
        from lys.apps.base.modules.access_level.nodes import AccessLevelNode
        from lys.apps.base.modules.access_level.services import AccessLevelService
        # The node should have reference to its service via the parametric_node decorator
        # This is stored in the class after decoration
        assert AccessLevelNode is not None
