"""
Unit tests for licensing subscription GraphQL nodes.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestSubscriptionNode:
    """Tests for SubscriptionNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode
        assert SubscriptionNode is not None

    def test_is_strawberry_type(self):
        from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode
        assert hasattr(SubscriptionNode, "__strawberry_definition__") or hasattr(SubscriptionNode, "_type_definition")
