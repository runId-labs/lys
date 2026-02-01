"""
Unit tests for base webservice module nodes.

Tests GraphQL node structure.
"""

import pytest


class TestRegisterWebservicesNode:
    """Tests for RegisterWebservicesNode."""

    def test_node_exists(self):
        """Test RegisterWebservicesNode class exists."""
        from lys.apps.base.modules.webservice.nodes import RegisterWebservicesNode
        assert RegisterWebservicesNode is not None

    def test_node_inherits_from_service_node(self):
        """Test RegisterWebservicesNode inherits from ServiceNode."""
        from lys.apps.base.modules.webservice.nodes import RegisterWebservicesNode
        from lys.core.graphql.nodes import ServiceNode
        assert issubclass(RegisterWebservicesNode, ServiceNode)

    def test_node_has_success_field(self):
        """Test RegisterWebservicesNode has success field."""
        from lys.apps.base.modules.webservice.nodes import RegisterWebservicesNode
        assert "success" in RegisterWebservicesNode.__annotations__

    def test_node_has_registered_count_field(self):
        """Test RegisterWebservicesNode has registered_count field."""
        from lys.apps.base.modules.webservice.nodes import RegisterWebservicesNode
        assert "registered_count" in RegisterWebservicesNode.__annotations__

    def test_node_has_message_field(self):
        """Test RegisterWebservicesNode has message field with default."""
        from lys.apps.base.modules.webservice.nodes import RegisterWebservicesNode
        assert "message" in RegisterWebservicesNode.__annotations__
        assert RegisterWebservicesNode.message == "Webservices registered successfully"


class TestWebserviceNode:
    """Tests for WebserviceNode."""

    def test_node_exists(self):
        """Test WebserviceNode class exists."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert WebserviceNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test WebserviceNode inherits from EntityNode."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(WebserviceNode, EntityNode)

    def test_node_has_id_field(self):
        """Test WebserviceNode has id field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "id" in WebserviceNode.__annotations__

    def test_node_has_code_field(self):
        """Test WebserviceNode has code field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "code" in WebserviceNode.__annotations__

    def test_node_has_enabled_field(self):
        """Test WebserviceNode has enabled field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "enabled" in WebserviceNode.__annotations__

    def test_node_has_created_at_field(self):
        """Test WebserviceNode has created_at field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "created_at" in WebserviceNode.__annotations__

    def test_node_has_updated_at_field(self):
        """Test WebserviceNode has updated_at field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "updated_at" in WebserviceNode.__annotations__

    def test_node_has_is_public_field(self):
        """Test WebserviceNode has is_public field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "is_public" in WebserviceNode.__annotations__

    def test_node_has_app_name_field(self):
        """Test WebserviceNode has app_name field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "app_name" in WebserviceNode.__annotations__

    def test_node_has_operation_type_field(self):
        """Test WebserviceNode has operation_type field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "operation_type" in WebserviceNode.__annotations__

    def test_node_has_ai_tool_field(self):
        """Test WebserviceNode has ai_tool field."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert "ai_tool" in WebserviceNode.__annotations__

    def test_node_has_access_levels_method(self):
        """Test WebserviceNode has access_levels method."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert hasattr(WebserviceNode, "access_levels")

    def test_node_has_order_by_attribute_map(self):
        """Test WebserviceNode has order_by_attribute_map."""
        from lys.apps.base.modules.webservice.nodes import WebserviceNode
        assert hasattr(WebserviceNode, "order_by_attribute_map")


class TestAccessedWebserviceNode:
    """Tests for AccessedWebserviceNode."""

    def test_node_exists(self):
        """Test AccessedWebserviceNode class exists."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert AccessedWebserviceNode is not None

    def test_node_inherits_from_entity_node(self):
        """Test AccessedWebserviceNode inherits from EntityNode."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        from lys.core.graphql.nodes import EntityNode
        assert issubclass(AccessedWebserviceNode, EntityNode)

    def test_node_has_id_field(self):
        """Test AccessedWebserviceNode has id field."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert "id" in AccessedWebserviceNode.__annotations__

    def test_node_has_code_field(self):
        """Test AccessedWebserviceNode has code field."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert "code" in AccessedWebserviceNode.__annotations__

    def test_node_has_enabled_field(self):
        """Test AccessedWebserviceNode has enabled field."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert "enabled" in AccessedWebserviceNode.__annotations__

    def test_node_has_is_public_field(self):
        """Test AccessedWebserviceNode has is_public field."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert "is_public" in AccessedWebserviceNode.__annotations__

    def test_node_has_user_access_levels_method(self):
        """Test AccessedWebserviceNode has user_access_levels method."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert hasattr(AccessedWebserviceNode, "user_access_levels")

    def test_node_has_order_by_attribute_map(self):
        """Test AccessedWebserviceNode has order_by_attribute_map."""
        from lys.apps.base.modules.webservice.nodes import AccessedWebserviceNode
        assert hasattr(AccessedWebserviceNode, "order_by_attribute_map")
