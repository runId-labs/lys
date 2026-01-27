"""
Unit tests for AI conversation GraphQL nodes.

Tests node structure.
"""

import pytest


class TestAIMessageNode:
    """Tests for AIMessageNode."""

    def test_node_exists(self):
        """Test AIMessageNode class exists."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert AIMessageNode is not None

    def test_node_inherits_from_service_node(self):
        """Test AIMessageNode inherits from ServiceNode."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        from lys.core.graphql.nodes import ServiceNode
        assert issubclass(AIMessageNode, ServiceNode)

    def test_node_has_content_field(self):
        """Test AIMessageNode has content field."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert "content" in AIMessageNode.__annotations__

    def test_node_has_conversation_id_field(self):
        """Test AIMessageNode has conversation_id field."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert "conversation_id" in AIMessageNode.__annotations__

    def test_node_has_tool_calls_count_field(self):
        """Test AIMessageNode has tool_calls_count field."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert "tool_calls_count" in AIMessageNode.__annotations__

    def test_node_has_tool_results_field(self):
        """Test AIMessageNode has tool_results field."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert "tool_results" in AIMessageNode.__annotations__

    def test_node_has_frontend_actions_field(self):
        """Test AIMessageNode has frontend_actions field."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert "frontend_actions" in AIMessageNode.__annotations__

    def test_node_has_message_field(self):
        """Test AIMessageNode has message field with default."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert "message" in AIMessageNode.__annotations__
        assert AIMessageNode.message == "AI response generated successfully"

    def test_node_has_default_tool_calls_count(self):
        """Test AIMessageNode has default tool_calls_count."""
        from lys.apps.ai.modules.conversation.nodes import AIMessageNode
        assert AIMessageNode.tool_calls_count == 0
