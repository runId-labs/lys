"""
Unit tests for Mollie GraphQL nodes.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestSubscribeToPlanResultNode:
    """Tests for SubscribeToPlanResultNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.mollie.nodes import SubscribeToPlanResultNode
        assert SubscribeToPlanResultNode is not None

    def test_has_success_field(self):
        from lys.apps.licensing.modules.mollie.nodes import SubscribeToPlanResultNode
        annotations = {}
        for cls in SubscribeToPlanResultNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "success" in annotations

    def test_has_checkout_url_field(self):
        from lys.apps.licensing.modules.mollie.nodes import SubscribeToPlanResultNode
        annotations = {}
        for cls in SubscribeToPlanResultNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "checkout_url" in annotations

    def test_has_error_field(self):
        from lys.apps.licensing.modules.mollie.nodes import SubscribeToPlanResultNode
        annotations = {}
        for cls in SubscribeToPlanResultNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "error" in annotations


class TestCancelSubscriptionResultNode:
    """Tests for CancelSubscriptionResultNode."""

    def test_node_exists(self):
        from lys.apps.licensing.modules.mollie.nodes import CancelSubscriptionResultNode
        assert CancelSubscriptionResultNode is not None

    def test_has_success_field(self):
        from lys.apps.licensing.modules.mollie.nodes import CancelSubscriptionResultNode
        annotations = {}
        for cls in CancelSubscriptionResultNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "success" in annotations

    def test_has_effective_date_field(self):
        from lys.apps.licensing.modules.mollie.nodes import CancelSubscriptionResultNode
        annotations = {}
        for cls in CancelSubscriptionResultNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "effective_date" in annotations

    def test_has_error_field(self):
        from lys.apps.licensing.modules.mollie.nodes import CancelSubscriptionResultNode
        annotations = {}
        for cls in CancelSubscriptionResultNode.__mro__:
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)
        assert "error" in annotations
