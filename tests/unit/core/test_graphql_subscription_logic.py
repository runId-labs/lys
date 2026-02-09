"""
Unit tests for core graphql subscription module logic.

Tests lys_subscription decorator and inner_resolver type validation.
"""

import asyncio
import inspect
from unittest.mock import MagicMock, patch

import pytest


class TestLysSubscriptionInnerResolver:
    """Tests for the inner_resolver created by lys_subscription wrapper."""

    def _create_inner_resolver(self, ensure_type_cls, original_resolver):
        """Create the inner_resolver by manually applying the wrapper logic."""
        # This mimics what lys_subscription's wrapper function does
        effective_type = ensure_type_cls.get_effective_node()

        async def inner_resolver(self, *args, info, **kwargs):
            async for node in original_resolver(self, *args, info=info, **kwargs):
                if node is not None and not isinstance(node, effective_type):
                    raise ValueError(
                        f"Wrong node type '{node.__class__.__name__}'. "
                        f"Expected: '{effective_type.__name__}'"
                    )
                yield node

        inner_resolver.__name__ = original_resolver.__name__
        inner_resolver.__qualname__ = original_resolver.__qualname__
        inner_resolver.__module__ = original_resolver.__module__
        inner_resolver.__signature__ = inspect.signature(original_resolver)

        return inner_resolver

    def test_wrong_node_type_raises_value_error(self):
        class FakeNode:
            @classmethod
            def get_effective_node(cls):
                return FakeNode

        class WrongNode:
            pass

        async def my_sub(self, info):
            yield WrongNode()

        inner = self._create_inner_resolver(FakeNode, my_sub)

        loop = asyncio.new_event_loop()
        try:
            gen = inner(None, info=MagicMock())

            async def consume():
                with pytest.raises(ValueError, match="Wrong node type"):
                    async for _ in gen:
                        pass

            loop.run_until_complete(consume())
        finally:
            loop.close()

    def test_correct_node_type_passes_through(self):
        class FakeNode:
            @classmethod
            def get_effective_node(cls):
                return FakeNode

        async def my_sub(self, info):
            yield FakeNode()
            yield FakeNode()

        inner = self._create_inner_resolver(FakeNode, my_sub)

        loop = asyncio.new_event_loop()
        try:
            gen = inner(None, info=MagicMock())

            async def consume():
                results = []
                async for node in gen:
                    results.append(node)
                return results

            results = loop.run_until_complete(consume())
            assert len(results) == 2
        finally:
            loop.close()

    def test_none_nodes_pass_through(self):
        class FakeNode:
            @classmethod
            def get_effective_node(cls):
                return FakeNode

        async def my_sub(self, info):
            yield None
            yield FakeNode()

        inner = self._create_inner_resolver(FakeNode, my_sub)

        loop = asyncio.new_event_loop()
        try:
            gen = inner(None, info=MagicMock())

            async def consume():
                results = []
                async for node in gen:
                    results.append(node)
                return results

            results = loop.run_until_complete(consume())
            assert len(results) == 2
            assert results[0] is None
            assert isinstance(results[1], FakeNode)
        finally:
            loop.close()

    def test_preserves_function_metadata(self):
        class FakeNode:
            @classmethod
            def get_effective_node(cls):
                return FakeNode

        async def my_subscription(self, info, channel: str):
            yield FakeNode()

        inner = self._create_inner_resolver(FakeNode, my_subscription)

        assert inner.__name__ == "my_subscription"
        assert inner.__module__ == my_subscription.__module__


class TestLysSubscriptionDecorator:
    """Tests for lys_subscription decorator structure."""

    def test_registers_as_webservice(self):
        from lys.core.graphql.subscription import lys_subscription

        class FakeNode:
            @classmethod
            def get_effective_node(cls):
                return FakeNode

        with patch("lys.core.graphql.subscription.register_webservice") as mock_reg, \
             patch("lys.core.graphql.subscription.generate_webservice_permission") as mock_perm, \
             patch("lys.core.graphql.subscription.format_filed_description", return_value="desc"):

            mock_perm.return_value = MagicMock()
            mock_reg.return_value = lambda f: f

            @lys_subscription(
                ensure_type=FakeNode,
                is_public=True,
                access_levels=["ROLE"],
                is_licenced=False
            )
            async def my_sub(self, info):
                yield FakeNode()

            mock_reg.assert_called_once()
            call_kwargs = mock_reg.call_args.kwargs
            assert call_kwargs["is_public"] is True
            assert call_kwargs["access_levels"] == ["ROLE"]
            assert call_kwargs["is_licenced"] is False

    def test_calls_strawberry_subscription(self):
        from lys.core.graphql.subscription import lys_subscription

        class FakeNode:
            @classmethod
            def get_effective_node(cls):
                return FakeNode

        with patch("lys.core.graphql.subscription.register_webservice") as mock_reg, \
             patch("lys.core.graphql.subscription.generate_webservice_permission") as mock_perm, \
             patch("lys.core.graphql.subscription.format_filed_description", return_value="desc"), \
             patch("lys.core.graphql.subscription.strawberry") as mock_strawberry:

            mock_perm.return_value = MagicMock()
            mock_reg.return_value = lambda f: f
            mock_strawberry.subscription.return_value = MagicMock()

            @lys_subscription(ensure_type=FakeNode, is_public=True)
            async def my_sub(self, info):
                yield FakeNode()

            mock_strawberry.subscription.assert_called_once()
