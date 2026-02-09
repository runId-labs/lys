"""
Unit tests for licensing subscription webservices.

Tests SubscriptionQuery structure.
"""

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestSubscriptionQuery:
    """Tests for SubscriptionQuery structure."""

    def test_query_exists(self):
        from lys.apps.licensing.modules.subscription.webservices import SubscriptionQuery
        assert SubscriptionQuery is not None

    def test_has_subscription_method(self):
        from lys.apps.licensing.modules.subscription.webservices import SubscriptionQuery
        assert hasattr(SubscriptionQuery, "subscription")
