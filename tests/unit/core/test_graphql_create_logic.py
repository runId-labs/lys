"""
Unit tests for core graphql create module logic.

Tests _creation_resolver_generator internal logic.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from lys.core.graphql.create import _creation_resolver_generator


class TestCreationResolverGenerator:
    """Tests for _creation_resolver_generator."""

    def _make_resolver(self, return_value=None, side_effect=None):
        """Create a real async function as resolver (AsyncMock lacks __qualname__)."""
        calls = []

        async def my_resolver(self, info):
            calls.append(info)
            if side_effect:
                side_effect()
            return return_value

        my_resolver._calls = calls
        return my_resolver

    def test_successful_creation_returns_node(self):
        mock_entity_obj = MagicMock()
        mock_node = MagicMock()

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.entity_class = type(mock_entity_obj)
        mock_ensure_type.from_obj.return_value = mock_node

        resolver_func = self._make_resolver(return_value=mock_entity_obj)
        inner = _creation_resolver_generator(resolver_func, mock_ensure_type)

        mock_info = MagicMock()
        mock_session = AsyncMock()
        mock_info.context.session = mock_session

        with patch("lys.core.graphql.create.check_access_to_object", new_callable=AsyncMock) as mock_check:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(inner(None, info=mock_info))
            finally:
                loop.close()

        assert len(resolver_func._calls) == 1
        mock_session.add.assert_called_once_with(mock_entity_obj)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(mock_entity_obj)
        mock_check.assert_awaited_once_with(mock_entity_obj, mock_info.context)
        mock_ensure_type.from_obj.assert_called_once_with(mock_entity_obj)
        assert result is mock_node

    def test_wrong_entity_type_raises_value_error(self):
        mock_entity_obj = MagicMock()

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        # Make isinstance check fail by using a different type
        mock_ensure_type.entity_class = str

        resolver_func = self._make_resolver(return_value=mock_entity_obj)
        inner = _creation_resolver_generator(resolver_func, mock_ensure_type)

        mock_info = MagicMock()
        mock_session = AsyncMock()
        mock_info.context.session = mock_session

        with patch("lys.core.graphql.create.check_access_to_object", new_callable=AsyncMock):
            loop = asyncio.new_event_loop()
            try:
                with pytest.raises(ValueError, match="Wrong entity type"):
                    loop.run_until_complete(inner(None, info=mock_info))
            finally:
                loop.close()

        # Session.add should NOT have been called since the type check failed
        mock_session.add.assert_not_called()

    def test_sets_app_manager_on_context(self):
        mock_entity_obj = MagicMock()

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.entity_class = type(mock_entity_obj)
        mock_ensure_type.from_obj.return_value = MagicMock()

        resolver_func = self._make_resolver(return_value=mock_entity_obj)
        inner = _creation_resolver_generator(resolver_func, mock_ensure_type)

        mock_info = MagicMock()
        mock_info.context.session = AsyncMock()

        with patch("lys.core.graphql.create.check_access_to_object", new_callable=AsyncMock):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(inner(None, info=mock_info))
            finally:
                loop.close()

        assert mock_info.context.app_manager == mock_ensure_type.app_manager

    def test_preserves_resolver_metadata(self):
        async def my_create_resolver(self, info):
            pass

        mock_ensure_type = MagicMock()

        inner = _creation_resolver_generator(my_create_resolver, mock_ensure_type)

        assert inner.__name__ == "my_create_resolver"
        assert inner.__qualname__ == my_create_resolver.__qualname__
        assert inner.__module__ == my_create_resolver.__module__

    def test_check_access_called_before_session_add(self):
        """Verify check_access_to_object is called before the object is added to the session."""
        mock_entity_obj = MagicMock()
        call_order = []

        mock_ensure_type = MagicMock()
        mock_ensure_type.app_manager = MagicMock()
        mock_ensure_type.entity_class = type(mock_entity_obj)
        mock_ensure_type.from_obj.return_value = MagicMock()

        resolver_func = self._make_resolver(return_value=mock_entity_obj)
        inner = _creation_resolver_generator(resolver_func, mock_ensure_type)

        mock_info = MagicMock()
        mock_session = AsyncMock()
        # session.add() is synchronous, so use a regular MagicMock for it
        mock_session.add = MagicMock(side_effect=lambda obj: call_order.append("add"))
        mock_info.context.session = mock_session

        async def mock_check(obj, context):
            call_order.append("check_access")

        with patch("lys.core.graphql.create.check_access_to_object", side_effect=mock_check):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(inner(None, info=mock_info))
            finally:
                loop.close()

        assert call_order == ["check_access", "add"]


class TestLysCreation:
    """Tests for lys_creation function."""

    def test_lys_creation_returns_field(self):
        from lys.core.graphql.create import lys_creation

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.create.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            result = lys_creation(ensure_type=mock_ensure_type, description="Create item")

            mock_lys_typed_field.assert_called_once()
            assert result is mock_lys_typed_field.return_value

    def test_lys_creation_passes_resolver_wrapper(self):
        from lys.core.graphql.create import lys_creation, _creation_resolver_generator

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.create.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_creation(ensure_type=mock_ensure_type)

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert call_kwargs["resolver_wrapper"] is _creation_resolver_generator

    def test_lys_creation_default_risk_level(self):
        """Default risk_level should be ToolRiskLevel.CREATE when no options provided."""
        from lys.core.consts.ai import ToolRiskLevel
        from lys.core.graphql.create import lys_creation

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.create.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_creation(ensure_type=mock_ensure_type)

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert call_kwargs["options"]["risk_level"] == ToolRiskLevel.CREATE

    def test_lys_creation_preserves_custom_risk_level(self):
        """When options already contain risk_level, it should not be overridden."""
        from lys.core.consts.ai import ToolRiskLevel
        from lys.core.graphql.create import lys_creation

        mock_ensure_type = MagicMock()

        with patch("lys.core.graphql.create.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_creation(
                ensure_type=mock_ensure_type,
                options={"risk_level": ToolRiskLevel.READ}
            )

            call_kwargs = mock_lys_typed_field.call_args.kwargs
            assert call_kwargs["options"]["risk_level"] == ToolRiskLevel.READ

    def test_lys_creation_does_not_mutate_original_options(self):
        """The original options dict should not be modified."""
        from lys.core.graphql.create import lys_creation

        mock_ensure_type = MagicMock()
        original_options = {"custom_key": "value"}

        with patch("lys.core.graphql.create.lys_typed_field") as mock_lys_typed_field:
            mock_lys_typed_field.return_value = MagicMock()

            lys_creation(ensure_type=mock_ensure_type, options=original_options)

        assert "risk_level" not in original_options
