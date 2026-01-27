"""
Unit tests for core graphql interfaces module.

Tests GraphQL interface classes.
"""

import pytest


class TestNodeInterface:
    """Tests for NodeInterface class."""

    def test_class_exists(self):
        """Test NodeInterface class exists."""
        from lys.core.graphql.interfaces import NodeInterface
        assert NodeInterface is not None

    def test_has_service_class_property(self):
        """Test NodeInterface has service_class property."""
        from lys.core.graphql.interfaces import NodeInterface
        assert "service_class" in dir(NodeInterface)

    def test_has_get_effective_node_method(self):
        """Test NodeInterface has get_effective_node method."""
        from lys.core.graphql.interfaces import NodeInterface
        assert hasattr(NodeInterface, "get_effective_node")


class TestEntityNodeInterface:
    """Tests for EntityNodeInterface class."""

    def test_class_exists(self):
        """Test EntityNodeInterface class exists."""
        from lys.core.graphql.interfaces import EntityNodeInterface
        assert EntityNodeInterface is not None

    def test_inherits_from_node_interface(self):
        """Test EntityNodeInterface inherits from NodeInterface."""
        from lys.core.graphql.interfaces import EntityNodeInterface, NodeInterface
        assert issubclass(EntityNodeInterface, NodeInterface)

    def test_has_entity_class_property(self):
        """Test EntityNodeInterface has entity_class property."""
        from lys.core.graphql.interfaces import EntityNodeInterface
        assert "entity_class" in dir(EntityNodeInterface)

    def test_has_order_by_attribute_map_property(self):
        """Test EntityNodeInterface has order_by_attribute_map property."""
        from lys.core.graphql.interfaces import EntityNodeInterface
        assert "order_by_attribute_map" in dir(EntityNodeInterface)

    def test_has_from_obj_method(self):
        """Test EntityNodeInterface has from_obj method."""
        from lys.core.graphql.interfaces import EntityNodeInterface
        assert hasattr(EntityNodeInterface, "from_obj")

    def test_has_build_list_connection_method(self):
        """Test EntityNodeInterface has build_list_connection method."""
        from lys.core.graphql.interfaces import EntityNodeInterface
        assert hasattr(EntityNodeInterface, "build_list_connection")


class TestQueryInterface:
    """Tests for QueryInterface class."""

    def test_class_exists(self):
        """Test QueryInterface class exists."""
        from lys.core.graphql.interfaces import QueryInterface
        assert QueryInterface is not None

    def test_can_subclass(self):
        """Test QueryInterface can be subclassed."""
        from lys.core.graphql.interfaces import QueryInterface

        class MyQuery(QueryInterface):
            pass

        assert issubclass(MyQuery, QueryInterface)


class TestMutationInterface:
    """Tests for MutationInterface class."""

    def test_class_exists(self):
        """Test MutationInterface class exists."""
        from lys.core.graphql.interfaces import MutationInterface
        assert MutationInterface is not None

    def test_can_subclass(self):
        """Test MutationInterface can be subclassed."""
        from lys.core.graphql.interfaces import MutationInterface

        class MyMutation(MutationInterface):
            pass

        assert issubclass(MyMutation, MutationInterface)


class TestSubscriptionInterface:
    """Tests for SubscriptionInterface class."""

    def test_class_exists(self):
        """Test SubscriptionInterface class exists."""
        from lys.core.graphql.interfaces import SubscriptionInterface
        assert SubscriptionInterface is not None

    def test_can_subclass(self):
        """Test SubscriptionInterface can be subclassed."""
        from lys.core.graphql.interfaces import SubscriptionInterface

        class MySubscription(SubscriptionInterface):
            pass

        assert issubclass(MySubscription, SubscriptionInterface)
