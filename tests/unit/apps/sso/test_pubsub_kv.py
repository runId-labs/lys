"""
Unit tests for PubSubManager key-value operations.

Tests cover:
- set_key with and without TTL
- get_key with string/bytes/None results
- delete_key
- get_and_delete_key (atomic GETDEL)
- Graceful behavior when Redis is not initialized

Test approach: Unit (mocked Redis async client)
"""

import pytest
from unittest.mock import AsyncMock, patch, PropertyMock

from lys.core.managers.pubsub import PubSubManager


@pytest.fixture
def pubsub():
    """Create a PubSubManager with a mocked async Redis client."""
    manager = PubSubManager.__new__(PubSubManager)
    manager._async_redis = AsyncMock()
    manager._sync_redis = None
    manager._channel_prefix = "test:"
    return manager


@pytest.fixture
def pubsub_uninitialized():
    """Create a PubSubManager without Redis (not initialized)."""
    manager = PubSubManager.__new__(PubSubManager)
    manager._async_redis = None
    manager._sync_redis = None
    manager._channel_prefix = "test:"
    return manager


class TestSetKey:
    """Tests for PubSubManager.set_key()."""

    @pytest.mark.asyncio
    async def test_set_key_without_ttl(self, pubsub):
        pubsub._async_redis.set.return_value = True
        result = await pubsub.set_key("mykey", "myvalue")
        assert result is True
        pubsub._async_redis.set.assert_called_once_with("mykey", "myvalue")

    @pytest.mark.asyncio
    async def test_set_key_with_ttl(self, pubsub):
        pubsub._async_redis.set.return_value = True
        result = await pubsub.set_key("mykey", "myvalue", ttl_seconds=600)
        assert result is True
        pubsub._async_redis.set.assert_called_once_with("mykey", "myvalue", ex=600)

    @pytest.mark.asyncio
    async def test_set_key_returns_false_on_failure(self, pubsub):
        pubsub._async_redis.set.return_value = None
        result = await pubsub.set_key("mykey", "myvalue")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_key_uninitialized_returns_false(self, pubsub_uninitialized):
        result = await pubsub_uninitialized.set_key("mykey", "myvalue")
        assert result is False


class TestGetKey:
    """Tests for PubSubManager.get_key()."""

    @pytest.mark.asyncio
    async def test_get_key_returns_string(self, pubsub):
        pubsub._async_redis.get.return_value = "myvalue"
        result = await pubsub.get_key("mykey")
        assert result == "myvalue"

    @pytest.mark.asyncio
    async def test_get_key_decodes_bytes(self, pubsub):
        pubsub._async_redis.get.return_value = b"myvalue"
        result = await pubsub.get_key("mykey")
        assert result == "myvalue"

    @pytest.mark.asyncio
    async def test_get_key_returns_none_for_missing(self, pubsub):
        pubsub._async_redis.get.return_value = None
        result = await pubsub.get_key("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_key_uninitialized_returns_none(self, pubsub_uninitialized):
        result = await pubsub_uninitialized.get_key("mykey")
        assert result is None


class TestDeleteKey:
    """Tests for PubSubManager.delete_key()."""

    @pytest.mark.asyncio
    async def test_delete_key_success(self, pubsub):
        pubsub._async_redis.delete.return_value = 1
        result = await pubsub.delete_key("mykey")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_key_not_found(self, pubsub):
        pubsub._async_redis.delete.return_value = 0
        result = await pubsub.delete_key("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_key_uninitialized_returns_false(self, pubsub_uninitialized):
        result = await pubsub_uninitialized.delete_key("mykey")
        assert result is False


class TestGetAndDeleteKey:
    """Tests for PubSubManager.get_and_delete_key() (atomic GETDEL)."""

    @pytest.mark.asyncio
    async def test_get_and_delete_returns_string(self, pubsub):
        pubsub._async_redis.getdel.return_value = "myvalue"
        result = await pubsub.get_and_delete_key("mykey")
        assert result == "myvalue"

    @pytest.mark.asyncio
    async def test_get_and_delete_decodes_bytes(self, pubsub):
        pubsub._async_redis.getdel.return_value = b"myvalue"
        result = await pubsub.get_and_delete_key("mykey")
        assert result == "myvalue"

    @pytest.mark.asyncio
    async def test_get_and_delete_returns_none_for_missing(self, pubsub):
        pubsub._async_redis.getdel.return_value = None
        result = await pubsub.get_and_delete_key("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_and_delete_uninitialized_returns_none(self, pubsub_uninitialized):
        result = await pubsub_uninitialized.get_and_delete_key("mykey")
        assert result is None
