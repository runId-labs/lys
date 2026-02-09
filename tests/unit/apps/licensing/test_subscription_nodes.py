"""
Unit tests for licensing subscription GraphQL nodes.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None

from lys.apps.licensing.modules.subscription.nodes import SubscriptionNode


def _get_resolver(field_name):
    """Get the wrapped resolver function from a Strawberry field."""
    return SubscriptionNode.__dict__[field_name].base_resolver.wrapped_func


def _make_node(entity_attrs):
    """Create a SubscriptionNode with a mock entity."""
    entity = MagicMock()
    for k, v in entity_attrs.items():
        setattr(entity, k, v)
    node = object.__new__(SubscriptionNode)
    node._entity = entity
    return node


class TestSubscriptionNode:
    """Tests for SubscriptionNode."""

    def test_node_exists(self):
        assert SubscriptionNode is not None

    def test_is_strawberry_type(self):
        assert hasattr(SubscriptionNode, "__strawberry_definition__") or hasattr(SubscriptionNode, "_type_definition")


class TestSubscriptionNodeFields:
    """Tests for SubscriptionNode computed fields."""

    def test_client_id_returns_global_id(self):
        node = _make_node({"client_id": "client-uuid-123"})
        result = _get_resolver("client_id")(node)
        assert result.node_id == "client-uuid-123"

    def test_plan_version_id_returns_global_id(self):
        node = _make_node({"plan_version_id": "version-uuid-456"})
        result = _get_resolver("plan_version_id")(node)
        assert result.node_id == "version-uuid-456"

    def test_pending_plan_version_id_returns_none_when_null(self):
        node = _make_node({"pending_plan_version_id": None})
        result = _get_resolver("pending_plan_version_id")(node)
        assert result is None

    def test_pending_plan_version_id_returns_global_id_when_set(self):
        node = _make_node({"pending_plan_version_id": "pending-uuid-789"})
        result = _get_resolver("pending_plan_version_id")(node)
        assert result.node_id == "pending-uuid-789"

    def test_has_pending_downgrade_true(self):
        node = _make_node({"has_pending_downgrade": True})
        result = _get_resolver("has_pending_downgrade")(node)
        assert result is True

    def test_has_pending_downgrade_false(self):
        node = _make_node({"has_pending_downgrade": False})
        result = _get_resolver("has_pending_downgrade")(node)
        assert result is False

    def test_is_free_when_no_provider(self):
        node = _make_node({"provider_subscription_id": None})
        result = _get_resolver("is_free")(node)
        assert result is True

    def test_is_not_free_when_has_provider(self):
        node = _make_node({"provider_subscription_id": "sub_12345"})
        result = _get_resolver("is_free")(node)
        assert result is False

    def test_plan_version_returns_node(self):
        mock_plan_version = MagicMock()
        node = _make_node({"plan_version": mock_plan_version})
        resolver = _get_resolver("plan_version")
        mock_info = MagicMock()

        with patch("lys.apps.licensing.modules.subscription.nodes.LicensePlanVersionNode") as mock_node_cls:
            mock_node_cls.from_obj.return_value = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(node, mock_info))
            finally:
                loop.close()

            mock_node_cls.from_obj.assert_called_once_with(mock_plan_version)

    def test_pending_plan_version_returns_none_when_null(self):
        node = _make_node({"pending_plan_version": None})
        resolver = _get_resolver("pending_plan_version")
        mock_info = MagicMock()

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(resolver(node, mock_info))
        finally:
            loop.close()

        assert result is None

    def test_pending_plan_version_returns_node_when_set(self):
        mock_pending = MagicMock()
        node = _make_node({"pending_plan_version": mock_pending})
        resolver = _get_resolver("pending_plan_version")
        mock_info = MagicMock()

        with patch("lys.apps.licensing.modules.subscription.nodes.LicensePlanVersionNode") as mock_node_cls:
            mock_node_cls.from_obj.return_value = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(node, mock_info))
            finally:
                loop.close()

            mock_node_cls.from_obj.assert_called_once_with(mock_pending)
            assert result is not None
