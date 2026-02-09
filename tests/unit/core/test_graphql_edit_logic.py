"""
Unit tests for core graphql edit module logic.

Tests _edition_resolver_generator internal logic.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from lys.core.errors import LysError
from lys.core.graphql.edit import _edition_resolver_generator


class TestEditionResolverGenerator:
    """Tests for _edition_resolver_generator."""

    def _make_resolver(self, side_effect=None):
        """Create a real async function as resolver (AsyncMock lacks __qualname__)."""
        calls = []

        async def my_resolver(self, obj, info):
            calls.append((obj, info))
            if side_effect:
                side_effect()

        my_resolver._calls = calls
        return my_resolver

    def test_entity_found_calls_resolver_and_returns_node(self):
        resolver_func = self._make_resolver()
        mock_entity_obj = MagicMock()
        mock_node = MagicMock()

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class = MagicMock()
        mock_ensure_type.from_obj.return_value = mock_node

        inner = _edition_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "test-uuid"

        mock_info = MagicMock()
        mock_session = AsyncMock()
        mock_info.context.session = mock_session

        with patch(
            "lys.core.graphql.edit.get_db_object_and_check_access", new_callable=AsyncMock
        ) as mock_get, patch(
            "lys.core.graphql.edit.check_access_to_object", new_callable=AsyncMock
        ) as mock_check:
            mock_get.return_value = mock_entity_obj

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert len(resolver_func._calls) == 1
        assert resolver_func._calls[0][0] is mock_entity_obj
        mock_check.assert_awaited_once_with(mock_entity_obj, mock_info.context)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(mock_entity_obj)
        mock_ensure_type.from_obj.assert_called_once_with(mock_entity_obj)
        assert result is mock_node

    def test_entity_not_found_raises_lys_error(self):
        resolver_func = self._make_resolver()
        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class.entity_class = "TestEntity"

        inner = _edition_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "nonexistent-uuid"

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch(
            "lys.core.graphql.edit.get_db_object_and_check_access", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            loop = asyncio.new_event_loop()
            try:
                with pytest.raises(LysError):
                    loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert len(resolver_func._calls) == 0

    def test_sets_app_manager_on_context(self):
        resolver_func = self._make_resolver()
        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class = MagicMock()
        mock_ensure_type.from_obj.return_value = MagicMock()

        inner = _edition_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "test-uuid"
        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch(
            "lys.core.graphql.edit.get_db_object_and_check_access", new_callable=AsyncMock
        ) as mock_get, patch(
            "lys.core.graphql.edit.check_access_to_object", new_callable=AsyncMock
        ):
            mock_get.return_value = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert mock_info.context.app_manager == mock_ensure_type.app_manager

    def test_preserves_resolver_metadata(self):
        async def my_edit_resolver(self, obj, info):
            pass

        mock_ensure_type = MagicMock()

        inner = _edition_resolver_generator(my_edit_resolver, mock_ensure_type)

        assert inner.__name__ == "my_edit_resolver"
        assert inner.__qualname__ == my_edit_resolver.__qualname__
        assert inner.__module__ == my_edit_resolver.__module__

    def test_passes_correct_args_to_get_db_object(self):
        """Verify get_db_object_and_check_access is called with correct parameters."""
        resolver_func = self._make_resolver()
        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class = MagicMock()
        mock_ensure_type.from_obj.return_value = MagicMock()

        inner = _edition_resolver_generator(resolver_func, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "specific-uuid-123"

        mock_info = MagicMock()
        mock_session = AsyncMock()
        mock_info.context.session = mock_session

        with patch(
            "lys.core.graphql.edit.get_db_object_and_check_access", new_callable=AsyncMock
        ) as mock_get, patch(
            "lys.core.graphql.edit.check_access_to_object", new_callable=AsyncMock
        ):
            mock_get.return_value = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        mock_get.assert_awaited_once_with(
            "specific-uuid-123",
            mock_ensure_type.service_class,
            mock_info.context,
            session=mock_session
        )

    def test_check_access_called_after_resolver(self):
        """Verify check_access_to_object is called after the resolver modifies the object."""
        call_order = []

        async def tracking_resolver(self, obj, info):
            call_order.append("resolver")

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.service_class = MagicMock()
        mock_ensure_type.from_obj.return_value = MagicMock()

        inner = _edition_resolver_generator(tracking_resolver, mock_ensure_type)

        mock_id = MagicMock()
        mock_id.node_id = "test-uuid"
        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        async def mock_check(obj, context):
            call_order.append("check_access")

        with patch(
            "lys.core.graphql.edit.get_db_object_and_check_access", new_callable=AsyncMock
        ) as mock_get, patch(
            "lys.core.graphql.edit.check_access_to_object", side_effect=mock_check
        ):
            mock_get.return_value = MagicMock()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(inner(None, id=mock_id, info=mock_info))
            finally:
                loop.close()

        assert call_order == ["resolver", "check_access"]

    def test_inner_resolver_signature_has_id_parameter(self):
        """Verify the generated inner resolver has an 'id' parameter with GlobalID annotation."""
        import inspect
        from strawberry import relay

        async def my_edit_resolver(self, obj, info):
            pass

        mock_ensure_type = MagicMock()

        inner = _edition_resolver_generator(my_edit_resolver, mock_ensure_type)

        sig = inspect.signature(inner)
        params = list(sig.parameters.keys())
        assert "id" in params
        assert sig.parameters["id"].annotation is relay.GlobalID


class TestLysEdition:
    """Tests for lys_edition function."""

    def test_lys_edition_returns_field(self):
        from lys.core.graphql.edit import lys_edition

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.edit.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            result = lys_edition(ensure_type=mock_ensure_type, description="Edit item")

            mock_lys_typed_field.assert_called_once()
            assert result is mock_lys_typed_field.return_value

    def test_lys_edition_passes_resolver_wrapper(self):
        from lys.core.graphql.edit import lys_edition, _edition_resolver_generator

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.edit.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_edition(ensure_type=mock_ensure_type)

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert call_kwargs["resolver_wrapper"] is _edition_resolver_generator

    def test_lys_edition_default_risk_level(self):
        """Default risk_level should be ToolRiskLevel.UPDATE when no options provided."""
        from lys.core.consts.ai import ToolRiskLevel
        from lys.core.graphql.edit import lys_edition

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.edit.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_edition(ensure_type=mock_ensure_type)

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert call_kwargs["options"]["risk_level"] == ToolRiskLevel.UPDATE

    def test_lys_edition_preserves_custom_risk_level(self):
        """When options already contain risk_level, it should not be overridden."""
        from lys.core.consts.ai import ToolRiskLevel
        from lys.core.graphql.edit import lys_edition

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.edit.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_edition(
                ensure_type=mock_ensure_type,
                options={"risk_level": ToolRiskLevel.READ}
            )

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert call_kwargs["options"]["risk_level"] == ToolRiskLevel.READ

    def test_lys_edition_does_not_mutate_original_options(self):
        """The original options dict should not be modified."""
        from lys.core.graphql.edit import lys_edition

        mock_ensure_type = MagicMock()
        original_options = {"custom_key": "value"}

        with patch("lys.core.graphql.edit.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_edition(ensure_type=mock_ensure_type, options=original_options)

        assert "risk_level" not in original_options
