"""
Unit tests for organization client nodes logic.

Tests ClientNode.open_requests() field.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from lys.apps.organization.modules.client.nodes import ClientNode


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


class TestClientNodeOpenRequestsField:
    """Tests for ClientNode.open_requests() field."""

    def test_returns_nodes_for_open_requests(self):
        node = _make_node({"id": "client-uuid"})
        resolver = _get_resolver("open_requests")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_request = MagicMock()
        mock_service = MagicMock()
        mock_service.get_open_for_client = AsyncMock(return_value=[mock_request])
        mock_info.context.app_manager.get_service.return_value = mock_service

        with patch("lys.apps.organization.modules.client.nodes.ClientRequestNode") as mock_node_cls:
            mock_node_cls.from_obj.return_value = MagicMock(name="ClientRequestNodeInstance")

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(resolver(node, mock_info))
            finally:
                loop.close()

            mock_info.context.app_manager.get_service.assert_called_once_with("client_request")
            mock_service.get_open_for_client.assert_awaited_once_with(
                "client-uuid", mock_info.context.session
            )
            mock_node_cls.from_obj.assert_called_once_with(mock_request)
            assert result == [mock_node_cls.from_obj.return_value]

    def test_returns_empty_list_when_no_open_requests(self):
        node = _make_node({"id": "client-uuid"})
        resolver = _get_resolver("open_requests")

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        mock_service = MagicMock()
        mock_service.get_open_for_client = AsyncMock(return_value=[])
        mock_info.context.app_manager.get_service.return_value = mock_service

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(resolver(node, mock_info))
        finally:
            loop.close()

        assert result == []
