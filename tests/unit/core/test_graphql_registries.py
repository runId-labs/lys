"""
Unit tests for core graphql registries module.

Tests GraphqlRegistry, register_query, register_mutation, register_subscription.
"""
import pytest
from unittest.mock import patch

from lys.core.graphql.registries import (
    GraphqlRegistry,
    register_query,
    register_mutation,
    register_subscription,
)
from lys.core.graphql.interfaces import QueryInterface, MutationInterface, SubscriptionInterface


class TestGraphqlRegistry:
    """Tests for GraphqlRegistry class."""

    def test_is_empty_when_new(self):
        """Test that a new registry is empty."""
        registry = GraphqlRegistry()
        assert registry.is_empty is True

    def test_not_empty_after_register_query(self):
        """Test that registry is not empty after registering a query."""
        registry = GraphqlRegistry()

        class FakeQuery(QueryInterface):
            pass

        registry.register_query("test", FakeQuery)
        assert registry.is_empty is False

    def test_not_empty_after_register_mutation(self):
        """Test that registry is not empty after registering a mutation."""
        registry = GraphqlRegistry()

        class FakeMutation(MutationInterface):
            pass

        registry.register_mutation("test", FakeMutation)
        assert registry.is_empty is False

    def test_not_empty_after_register_subscription(self):
        """Test that registry is not empty after registering a subscription."""
        registry = GraphqlRegistry()

        class FakeSubscription(SubscriptionInterface):
            pass

        registry.register_subscription("test", FakeSubscription)
        assert registry.is_empty is False

    def test_register_subscription_adds_to_subscriptions(self):
        """Test that register_subscription adds the class to subscriptions dict."""
        registry = GraphqlRegistry()

        class FakeSubscription(SubscriptionInterface):
            pass

        registry.register_subscription("schema1", FakeSubscription)
        assert "schema1" in registry.subscriptions
        assert FakeSubscription in registry.subscriptions["schema1"]


class TestRegisterQueryDecorator:
    """Tests for register_query decorator."""

    def test_valid_query_class_is_registered(self):
        """Test that a valid query class is registered."""
        registry = GraphqlRegistry()

        @register_query(register=registry)
        class TestQuery(QueryInterface):
            pass

        assert TestQuery in registry.queries.get("graphql", [])

    def test_invalid_query_class_name_raises(self):
        """Test that a class not ending in 'Query' raises ValueError."""
        registry = GraphqlRegistry()
        with pytest.raises(ValueError, match="must end with 'Query'"):
            @register_query(register=registry)
            class TestHandler(QueryInterface):
                pass


class TestRegisterMutationDecorator:
    """Tests for register_mutation decorator."""

    def test_valid_mutation_class_is_registered(self):
        """Test that a valid mutation class is registered."""
        registry = GraphqlRegistry()

        @register_mutation(register=registry)
        class TestMutation(MutationInterface):
            pass

        assert TestMutation in registry.mutations.get("graphql", [])

    def test_invalid_mutation_class_name_raises(self):
        """Test that a class not ending in 'Mutation' raises ValueError."""
        registry = GraphqlRegistry()
        with pytest.raises(ValueError, match="must end with 'Mutation'"):
            @register_mutation(register=registry)
            class TestHandler(MutationInterface):
                pass


class TestRegisterSubscriptionDecorator:
    """Tests for register_subscription decorator."""

    def test_valid_subscription_class_is_registered(self):
        """Test that a valid subscription class is registered."""
        registry = GraphqlRegistry()

        @register_subscription(register=registry)
        class TestSubscription(SubscriptionInterface):
            pass

        assert TestSubscription in registry.subscriptions.get("graphql", [])

    def test_invalid_subscription_class_name_raises(self):
        """Test that a class not ending in 'Subscription' raises ValueError."""
        registry = GraphqlRegistry()
        with pytest.raises(ValueError, match="must end with 'Subscription'"):
            @register_subscription(register=registry)
            class TestHandler(SubscriptionInterface):
                pass
