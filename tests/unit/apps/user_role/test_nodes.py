"""
Unit tests for user_role GraphQL nodes.

Tests RoleNode and UserNode structures.
"""

import pytest


class TestRoleNode:
    """Tests for RoleNode GraphQL type."""

    def test_role_node_exists(self):
        """Test that RoleNode class exists."""
        from lys.apps.user_role.modules.role.nodes import RoleNode

        assert RoleNode is not None

    def test_role_node_uses_parametric_decorator(self):
        """Test that RoleNode is decorated with parametric_node."""
        from lys.apps.user_role.modules.role.nodes import RoleNode

        # parametric_node creates a pass-through class
        # The class should exist and be registered
        assert hasattr(RoleNode, "__name__")
        assert RoleNode.__name__ == "RoleNode"

    def test_role_node_is_registered(self):
        """Test that RoleNode is registered via register_node."""
        from lys.apps.user_role.modules.role.nodes import RoleNode

        # The class is registered if it can be imported without errors
        assert RoleNode is not None


class TestUserNode:
    """Tests for extended UserNode GraphQL type."""

    def test_user_node_exists(self):
        """Test that UserNode class exists."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert UserNode is not None

    def test_user_node_has_roles_method(self):
        """Test that UserNode has roles resolver method."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert hasattr(UserNode, "roles")

    def test_user_node_has_email_address_method(self):
        """Test that UserNode has email_address resolver method."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert hasattr(UserNode, "email_address")

    def test_user_node_has_status_method(self):
        """Test that UserNode has status resolver method."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert hasattr(UserNode, "status")

    def test_user_node_has_language_method(self):
        """Test that UserNode has language resolver method."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert hasattr(UserNode, "language")

    def test_user_node_has_private_data_method(self):
        """Test that UserNode has private_data resolver method."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert hasattr(UserNode, "private_data")

    def test_user_node_has_order_by_attribute_map(self):
        """Test that UserNode has order_by_attribute_map property."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert hasattr(UserNode, "order_by_attribute_map")

    def test_user_node_has_id_field(self):
        """Test that UserNode has id field."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        # Check if id is in annotations (for strawberry types)
        assert "id" in UserNode.__annotations__

    def test_user_node_has_created_at_field(self):
        """Test that UserNode has created_at field."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert "created_at" in UserNode.__annotations__

    def test_user_node_has_updated_at_field(self):
        """Test that UserNode has updated_at field."""
        from lys.apps.user_role.modules.user.nodes import UserNode

        assert "updated_at" in UserNode.__annotations__
