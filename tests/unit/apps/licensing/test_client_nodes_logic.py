"""
Unit tests for licensing client nodes logic.

Tests ClientNode fields: subscription(), license_plan(), owner_id.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None

from lys.apps.licensing.modules.client.nodes import ClientNode


def _get_resolver(field_name):
    """Get the wrapped resolver function from a Strawberry field."""
    return ClientNode.__dict__[field_name].base_resolver.wrapped_func


def _make_node(entity_attrs):
    """Create a ClientNode with a mock entity."""
    entity = MagicMock()
    for k, v in entity_attrs.items():
        setattr(entity, k, v)
    node = object.__new__(ClientNode)
    node._entity = entity
    return node


class TestClientNodeSubscriptionField:
    """Tests for ClientNode.subscription() field."""

    def test_subscription_returns_node_when_found(self):
        node = _make_node({"id": "client-uuid"})
        resolver = _get_resolver("subscription")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_subscription = MagicMock()
        mock_sub_service = MagicMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=mock_subscription)

        mock_service_class = MagicMock()
        mock_service_class.app_manager.get_service.return_value = mock_sub_service

        with patch.object(ClientNode, "service_class", mock_service_class):
            with patch("lys.apps.licensing.modules.client.nodes.SubscriptionNode") as mock_sub_node:
                mock_sub_node.from_obj.return_value = MagicMock(name="SubscriptionNodeInstance")

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(resolver(node, mock_info))
                finally:
                    loop.close()

                mock_sub_node.from_obj.assert_called_once_with(mock_subscription)
                assert result is not None

    def test_subscription_returns_none_when_not_found(self):
        node = _make_node({"id": "client-uuid"})
        resolver = _get_resolver("subscription")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_sub_service = MagicMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=None)

        mock_service_class = MagicMock()
        mock_service_class.app_manager.get_service.return_value = mock_sub_service

        with patch.object(ClientNode, "service_class", mock_service_class):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(node, mock_info))
            finally:
                loop.close()

            assert result is None


class TestClientNodeLicensePlanField:
    """Tests for ClientNode.license_plan() field."""

    def test_license_plan_returns_node_when_found(self):
        node = _make_node({"id": "client-uuid"})
        resolver = _get_resolver("license_plan")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_subscription = MagicMock()
        mock_subscription.plan = MagicMock()

        mock_sub_service = MagicMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=mock_subscription)

        mock_service_class = MagicMock()
        mock_service_class.app_manager.get_service.return_value = mock_sub_service

        with patch.object(ClientNode, "service_class", mock_service_class):
            with patch("lys.apps.licensing.modules.client.nodes.LicensePlanNode") as mock_plan_node:
                mock_plan_node.from_obj.return_value = MagicMock()

                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(resolver(node, mock_info))
                finally:
                    loop.close()

                mock_plan_node.from_obj.assert_called_once_with(mock_subscription.plan)
                assert result is not None

    def test_license_plan_returns_none_when_no_subscription(self):
        node = _make_node({"id": "client-uuid"})
        resolver = _get_resolver("license_plan")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_sub_service = MagicMock()
        mock_sub_service.get_client_subscription = AsyncMock(return_value=None)

        mock_service_class = MagicMock()
        mock_service_class.app_manager.get_service.return_value = mock_sub_service

        with patch.object(ClientNode, "service_class", mock_service_class):
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(node, mock_info))
            finally:
                loop.close()

            assert result is None


class TestClientNodeOwnerIdField:
    """Tests for ClientNode.owner_id field."""

    def test_owner_id_returns_global_id(self):
        node = _make_node({"owner_id": "user-uuid-123"})
        resolver = _get_resolver("owner_id")

        result = resolver(node)
        assert result.node_id == "user-uuid-123"
