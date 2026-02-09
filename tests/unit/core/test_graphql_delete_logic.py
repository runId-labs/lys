"""
Unit tests for core graphql delete module logic.

Tests _delete_resolver_generator internal logic.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from lys.core.errors import LysError
from lys.core.graphql.delete import _delete_resolver_generator


class TestDeleteResolverGenerator:
    """Tests for _delete_resolver_generator."""

    def _make_resolver(self, side_effect=None):
        """Create a real async function as resolver (AsyncMock lacks __qualname__)."""
        calls = []

        async def my_resolver(self, obj, info):
            calls.append((obj, info))
            if side_effect:
                side_effect()

        my_resolver._calls = calls
        return my_resolver

    def test_entity_found_calls_resolver_and_deletes(self):
        resolver_func = self._make_resolver()
        mock_entity_obj = MagicMock()

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class = MagicMock()

        inner = _delete_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "test-uuid"

        mock_info = MagicMock()
        mock_session = AsyncMock()
        mock_info.context.session = mock_session

        with patch("lys.core.graphql.delete.get_db_object_and_check_access", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_entity_obj

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert len(resolver_func._calls) == 1
        mock_session.delete.assert_called_once_with(mock_entity_obj)
        assert result.succeed is True

    def test_entity_not_found_raises_lys_error(self):
        resolver_func = self._make_resolver()
        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class.entity_class = "TestEntity"

        inner = _delete_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "nonexistent-uuid"

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch("lys.core.graphql.delete.get_db_object_and_check_access", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            loop = asyncio.new_event_loop()
            try:
                with pytest.raises(LysError):
                    loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert len(resolver_func._calls) == 0

    def test_preserves_resolver_metadata(self):
        async def my_delete_resolver(self, obj, info):
            pass

        mock_ensure_type = MagicMock()

        inner = _delete_resolver_generator(my_delete_resolver, mock_ensure_type)

        assert inner.__name__ == "my_delete_resolver"
        assert inner.__qualname__ == my_delete_resolver.__qualname__
        assert inner.__module__ == my_delete_resolver.__module__

    def test_sets_app_manager_on_context(self):
        resolver_func = self._make_resolver()
        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()

        inner = _delete_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "test-uuid"
        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch("lys.core.graphql.delete.get_db_object_and_check_access", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert mock_info.context.app_manager == mock_ensure_type.app_manager


class TestLysDelete:
    """Tests for lys_delete function."""

    def test_lys_delete_returns_field(self):
        from lys.core.graphql.delete import lys_delete

        mock_ensure_type = MagicMock()
        mock_ensure_type.get_effective_node.return_value = mock_ensure_type

        with patch("lys.core.graphql.delete.lys_typed_field") as mock_lys_typed_field:
            mock_field = MagicMock()
            mock_field.base_resolver = MagicMock()
            mock_lys_typed_field.return_value = mock_field

            result = lys_delete(ensure_type=mock_ensure_type, description="Delete item")

            mock_lys_typed_field.assert_called_once()
            assert result is mock_field

    def test_lys_delete_public_description(self):
        from lys.core.graphql.delete import lys_delete

        mock_ensure_type = MagicMock()
        mock_ensure_type.get_effective_node.return_value = mock_ensure_type

        with patch("lys.core.graphql.delete.lys_typed_field") as mock_lys_typed_field:
            mock_field = MagicMock()
            mock_field.base_resolver = MagicMock()
            mock_lys_typed_field.return_value = mock_field

            lys_delete(ensure_type=mock_ensure_type, is_public=True, description="Test")

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert "PUBLIC" in call_kwargs["description"]

    def test_lys_delete_access_levels_description(self):
        from lys.core.graphql.delete import lys_delete

        mock_ensure_type = MagicMock()
        mock_ensure_type.get_effective_node.return_value = mock_ensure_type

        with patch("lys.core.graphql.delete.lys_typed_field") as mock_lys_typed_field:
            mock_field = MagicMock()
            mock_field.base_resolver = MagicMock()
            mock_lys_typed_field.return_value = mock_field

            lys_delete(
                ensure_type=mock_ensure_type,
                access_levels=["ADMIN", "MANAGER"],
                description="Delete"
            )

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert "ADMIN" in call_kwargs["description"]
            assert "MANAGER" in call_kwargs["description"]

    def test_lys_delete_super_user_only_description(self):
        from lys.core.graphql.delete import lys_delete

        mock_ensure_type = MagicMock()
        mock_ensure_type.get_effective_node.return_value = mock_ensure_type

        with patch("lys.core.graphql.delete.lys_typed_field") as mock_lys_typed_field:
            mock_field = MagicMock()
            mock_field.base_resolver = MagicMock()
            mock_lys_typed_field.return_value = mock_field

            lys_delete(ensure_type=mock_ensure_type, description="Delete")

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert "SUPER USER" in call_kwargs["description"]
