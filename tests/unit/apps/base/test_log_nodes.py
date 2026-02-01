"""
Unit tests for base log module nodes.

Tests GraphQL node structure.
"""

import pytest
from strawberry.types.fields.resolver import StrawberryResolver


class TestLogNode:
    """Tests for LogNode."""

    def test_node_exists(self):
        """Test LogNode class exists."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert LogNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test LogNode inherits from EntityNode."""
        from lys.apps.base.modules.log.nodes import LogNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(LogNode, EntityNode)

    def test_node_has_strawberry_definition(self):
        """Test LogNode has strawberry definition."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert hasattr(LogNode, "__strawberry_definition__")

    def test_node_has_id_field(self):
        """Test LogNode has id field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "id" in LogNode.__annotations__

    def test_node_has_created_at_field(self):
        """Test LogNode has created_at field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "created_at" in LogNode.__annotations__

    def test_node_has_updated_at_field(self):
        """Test LogNode has updated_at field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "updated_at" in LogNode.__annotations__

    def test_node_has_message_field(self):
        """Test LogNode has message field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "message" in LogNode.__annotations__

    def test_node_has_file_name_field(self):
        """Test LogNode has file_name field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "file_name" in LogNode.__annotations__

    def test_node_has_line_field(self):
        """Test LogNode has line field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "line" in LogNode.__annotations__

    def test_node_has_traceback_field(self):
        """Test LogNode has traceback field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "traceback" in LogNode.__annotations__

    def test_node_has_context_field(self):
        """Test LogNode has context field."""
        from lys.apps.base.modules.log.nodes import LogNode
        assert "context" in LogNode.__annotations__
