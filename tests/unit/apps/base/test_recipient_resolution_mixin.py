"""
Unit tests for RecipientResolutionMixin (base).

Tests the foundational recipient resolution logic:
- triggered_by + additional_user_ids
- deduplication
- None handling
"""
import inspect

import pytest

from lys.apps.base.mixins.recipient_resolution import RecipientResolutionMixin


class TestRecipientResolutionMixinStructure:
    """Verify class structure and method signatures."""

    def test_class_exists(self):
        assert inspect.isclass(RecipientResolutionMixin)

    def test_has_resolve_recipients(self):
        assert hasattr(RecipientResolutionMixin, "_resolve_recipients")

    def test_resolve_recipients_is_async(self):
        assert inspect.iscoroutinefunction(RecipientResolutionMixin._resolve_recipients)

    def test_resolve_recipients_is_classmethod(self):
        assert isinstance(
            inspect.getattr_static(RecipientResolutionMixin, "_resolve_recipients"),
            classmethod,
        )

    def test_has_resolve_recipients_sync(self):
        assert hasattr(RecipientResolutionMixin, "_resolve_recipients_sync")

    def test_resolve_recipients_sync_is_sync(self):
        assert not inspect.iscoroutinefunction(RecipientResolutionMixin._resolve_recipients_sync)

    def test_resolve_recipients_sync_is_classmethod(self):
        assert isinstance(
            inspect.getattr_static(RecipientResolutionMixin, "_resolve_recipients_sync"),
            classmethod,
        )

    def test_resolve_recipients_signature(self):
        sig = inspect.signature(RecipientResolutionMixin._resolve_recipients)
        params = list(sig.parameters.keys())
        assert "app_manager" in params
        assert "session" in params
        assert "type_entity" in params
        assert "triggered_by_user_id" in params
        assert "additional_user_ids" in params

    def test_resolve_recipients_sync_signature(self):
        sig = inspect.signature(RecipientResolutionMixin._resolve_recipients_sync)
        params = list(sig.parameters.keys())
        assert "app_manager" in params
        assert "session" in params
        assert "type_entity" in params
        assert "triggered_by_user_id" in params
        assert "additional_user_ids" in params


class TestRecipientResolutionMixinAsync:
    """Tests for async _resolve_recipients."""

    @pytest.mark.asyncio
    async def test_triggered_by_only(self):
        result = await RecipientResolutionMixin._resolve_recipients(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert result == ["user-1"]

    @pytest.mark.asyncio
    async def test_additional_only(self):
        result = await RecipientResolutionMixin._resolve_recipients(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id=None,
            additional_user_ids=["user-2", "user-3"],
        )
        assert set(result) == {"user-2", "user-3"}

    @pytest.mark.asyncio
    async def test_triggered_by_and_additional(self):
        result = await RecipientResolutionMixin._resolve_recipients(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id="user-1",
            additional_user_ids=["user-2", "user-3"],
        )
        assert set(result) == {"user-1", "user-2", "user-3"}

    @pytest.mark.asyncio
    async def test_deduplication(self):
        result = await RecipientResolutionMixin._resolve_recipients(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id="user-1",
            additional_user_ids=["user-1", "user-2"],
        )
        assert set(result) == {"user-1", "user-2"}
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_both_none(self):
        result = await RecipientResolutionMixin._resolve_recipients(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id=None,
            additional_user_ids=None,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_additional(self):
        result = await RecipientResolutionMixin._resolve_recipients(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id=None,
            additional_user_ids=[],
        )
        assert result == []


class TestRecipientResolutionMixinSync:
    """Tests for sync _resolve_recipients_sync."""

    def test_triggered_by_only(self):
        result = RecipientResolutionMixin._resolve_recipients_sync(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert result == ["user-1"]

    def test_additional_only(self):
        result = RecipientResolutionMixin._resolve_recipients_sync(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id=None,
            additional_user_ids=["user-2", "user-3"],
        )
        assert set(result) == {"user-2", "user-3"}

    def test_deduplication(self):
        result = RecipientResolutionMixin._resolve_recipients_sync(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id="user-1",
            additional_user_ids=["user-1", "user-2"],
        )
        assert set(result) == {"user-1", "user-2"}
        assert len(result) == 2

    def test_both_none(self):
        result = RecipientResolutionMixin._resolve_recipients_sync(
            app_manager=None,
            session=None,
            type_entity=None,
            triggered_by_user_id=None,
            additional_user_ids=None,
        )
        assert result == []
