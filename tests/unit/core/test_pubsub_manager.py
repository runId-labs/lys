"""
Unit tests for PubSubManager.

Tests cover:
- Structure: class methods and attributes exist
- Channel/message building: prefix and JSON formatting
- Async operations: publish, subscribe (with fakeredis)
- Sync operations: publish_sync (with fakeredis)
- Idempotency: set_if_not_exists, exists (with fakeredis)
- Distributed locking: acquire, contention, release (with fakeredis)
- Lifecycle: initialize, shutdown (async and sync)
- Graceful degradation: uninitialized state behavior
"""
import asyncio
import inspect
import json

import pytest
import fakeredis

from lys.core.managers.pubsub import PubSubManager


# ==================== Fixtures ====================

@pytest.fixture
def fake_server():
    """Shared fakeredis server for state isolation between tests."""
    return fakeredis.FakeServer()


@pytest.fixture
def manager():
    """PubSubManager instance without initialization."""
    return PubSubManager(redis_url="redis://fake:6379")


@pytest.fixture
def async_manager(fake_server):
    """PubSubManager with fake async Redis injected."""
    mgr = PubSubManager(redis_url="redis://fake:6379")
    mgr._async_redis = fakeredis.FakeAsyncRedis(server=fake_server)
    return mgr


@pytest.fixture
def sync_manager(fake_server):
    """PubSubManager with fake sync Redis injected."""
    mgr = PubSubManager(redis_url="redis://fake:6379")
    mgr._sync_redis = fakeredis.FakeRedis(server=fake_server)
    return mgr


# ==================== Structure Tests ====================

class TestPubSubManagerStructure:
    """Tests for PubSubManager class structure."""

    def test_manager_exists(self):
        assert PubSubManager is not None

    def test_constructor_accepts_redis_url(self):
        manager = PubSubManager(redis_url="redis://localhost:6379")
        assert manager.redis_url == "redis://localhost:6379"

    def test_constructor_default_channel_prefix(self):
        manager = PubSubManager(redis_url="redis://localhost:6379")
        assert manager.channel_prefix == "signal"

    def test_constructor_custom_channel_prefix(self):
        manager = PubSubManager(redis_url="redis://localhost:6379", channel_prefix="custom")
        assert manager.channel_prefix == "custom"

    def test_has_publish_method(self):
        assert hasattr(PubSubManager, "publish")
        assert inspect.iscoroutinefunction(PubSubManager.publish)

    def test_has_subscribe_method(self):
        assert hasattr(PubSubManager, "subscribe")
        assert inspect.isasyncgenfunction(PubSubManager.subscribe)

    def test_has_set_if_not_exists_method(self):
        assert hasattr(PubSubManager, "set_if_not_exists")
        assert inspect.iscoroutinefunction(PubSubManager.set_if_not_exists)

    def test_has_exists_method(self):
        assert hasattr(PubSubManager, "exists")
        assert inspect.iscoroutinefunction(PubSubManager.exists)

    def test_has_shutdown_method(self):
        assert hasattr(PubSubManager, "shutdown")
        assert inspect.iscoroutinefunction(PubSubManager.shutdown)

    def test_has_initialize_method(self):
        assert hasattr(PubSubManager, "initialize")
        assert inspect.iscoroutinefunction(PubSubManager.initialize)

    def test_has_publish_sync_method(self):
        assert hasattr(PubSubManager, "publish_sync")
        assert callable(PubSubManager.publish_sync)

    def test_has_initialize_sync_method(self):
        assert hasattr(PubSubManager, "initialize_sync")
        assert callable(PubSubManager.initialize_sync)

    def test_has_shutdown_sync_method(self):
        assert hasattr(PubSubManager, "shutdown_sync")
        assert callable(PubSubManager.shutdown_sync)

    def test_has_distributed_lock_method(self):
        assert hasattr(PubSubManager, "distributed_lock")
        assert inspect.iscoroutinefunction(PubSubManager.distributed_lock)


# ==================== Channel Building ====================

class TestPubSubManagerChannelBuilding:
    """Tests for channel and message building helpers."""

    def test_build_channel_with_prefix(self):
        manager = PubSubManager(redis_url="redis://localhost:6379", channel_prefix="signal")
        assert manager._build_channel("user:123") == "signal:user:123"

    def test_build_channel_without_prefix(self):
        manager = PubSubManager(redis_url="redis://localhost:6379", channel_prefix="")
        assert manager._build_channel("user:123") == "user:123"

    def test_build_message_with_params(self):
        manager = PubSubManager(redis_url="redis://localhost:6379")
        msg = json.loads(manager._build_message("EVENT", {"key": "value"}))
        assert msg["signal"] == "EVENT"
        assert msg["params"] == {"key": "value"}

    def test_build_message_without_params(self):
        manager = PubSubManager(redis_url="redis://localhost:6379")
        msg = json.loads(manager._build_message("EVENT"))
        assert msg["signal"] == "EVENT"
        assert msg["params"] == {}


# ==================== Async Publish ====================

@pytest.mark.asyncio
class TestAsyncPublish:
    """Test async publish with fakeredis."""

    async def test_publish_returns_subscriber_count(self, async_manager):
        """Publish returns 0 when no subscribers are listening."""
        result = await async_manager.publish("user:1", "CREATED", {"id": "abc"})
        assert result == 0

    async def test_publish_message_reaches_subscriber(self, async_manager, fake_server):
        """Published message is received by a raw subscriber on the prefixed channel."""
        raw = fakeredis.FakeAsyncRedis(server=fake_server)
        pubsub = raw.pubsub()
        await pubsub.subscribe("signal:user:42")

        # Consume subscribe confirmation
        confirm = await pubsub.get_message(timeout=1)
        assert confirm["type"] == "subscribe"

        result = await async_manager.publish("user:42", "TEST", {"k": "v"})
        assert result == 1

        msg = await pubsub.get_message(timeout=1)
        assert msg["type"] == "message"
        payload = json.loads(msg["data"])
        assert payload["signal"] == "TEST"
        assert payload["params"] == {"k": "v"}

        await pubsub.unsubscribe("signal:user:42")
        await pubsub.aclose()
        await raw.aclose()

    async def test_publish_without_params(self, async_manager):
        """Publish with no params sends empty dict."""
        result = await async_manager.publish("ch", "EVT")
        assert isinstance(result, int)

    async def test_publish_raises_when_not_initialized(self, manager):
        """Publish raises RuntimeError when async client not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.publish("ch", "SIG")


# ==================== Async Subscribe ====================

@pytest.mark.asyncio
class TestAsyncSubscribe:
    """Test async subscribe with fakeredis."""

    async def test_subscribe_receives_published_message(self, async_manager, fake_server):
        """Subscriber yields published messages as parsed dicts."""
        received = []

        async def subscriber():
            async for msg in async_manager.subscribe("user:1"):
                received.append(msg)
                break

        sub_task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.1)

        publisher = fakeredis.FakeAsyncRedis(server=fake_server)
        await publisher.publish(
            "signal:user:1",
            json.dumps({"signal": "HELLO", "params": {"name": "test"}})
        )
        await publisher.aclose()

        await asyncio.wait_for(sub_task, timeout=2.0)
        assert len(received) == 1
        assert received[0]["signal"] == "HELLO"
        assert received[0]["params"] == {"name": "test"}

    async def test_subscribe_receives_multiple_messages(self, async_manager, fake_server):
        """Subscriber yields multiple sequential messages in order."""
        received = []

        async def subscriber():
            async for msg in async_manager.subscribe("ch"):
                received.append(msg)
                if len(received) >= 3:
                    break

        sub_task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.1)

        publisher = fakeredis.FakeAsyncRedis(server=fake_server)
        for i in range(3):
            await publisher.publish(
                "signal:ch",
                json.dumps({"signal": f"MSG_{i}", "params": {}})
            )
        await publisher.aclose()

        await asyncio.wait_for(sub_task, timeout=2.0)
        assert len(received) == 3
        assert [m["signal"] for m in received] == ["MSG_0", "MSG_1", "MSG_2"]

    async def test_subscribe_skips_invalid_json(self, async_manager, fake_server):
        """Subscriber skips invalid JSON messages and continues listening."""
        received = []

        async def subscriber():
            async for msg in async_manager.subscribe("ch"):
                received.append(msg)
                if len(received) >= 1:
                    break

        sub_task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.1)

        publisher = fakeredis.FakeAsyncRedis(server=fake_server)
        await publisher.publish("signal:ch", "not-valid-json{{{")
        await publisher.publish(
            "signal:ch",
            json.dumps({"signal": "VALID", "params": {}})
        )
        await publisher.aclose()

        await asyncio.wait_for(sub_task, timeout=2.0)
        assert len(received) == 1
        assert received[0]["signal"] == "VALID"

    async def test_subscribe_raises_when_not_initialized(self, manager):
        """Subscribe raises RuntimeError when async client not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            async for _ in manager.subscribe("ch"):
                pass


# ==================== Sync Operations ====================

class TestSyncPublish:
    """Test sync publish with fakeredis."""

    def test_publish_sync_returns_subscriber_count(self, sync_manager):
        """Sync publish returns subscriber count (0 when no subscribers)."""
        result = sync_manager.publish_sync("user:1", "EVENT", {"id": "1"})
        assert result == 0

    def test_publish_sync_builds_correct_message(self, sync_manager, fake_server):
        """Sync publish sends correct JSON to prefixed channel."""
        raw = fakeredis.FakeRedis(server=fake_server)
        pubsub = raw.pubsub()
        pubsub.subscribe("signal:user:99")
        # Consume subscribe confirmation
        pubsub.get_message()

        result = sync_manager.publish_sync("user:99", "IMPORT_DONE", {"file_id": "f1"})
        assert result == 1

        msg = pubsub.get_message()
        assert msg["type"] == "message"
        payload = json.loads(msg["data"])
        assert payload["signal"] == "IMPORT_DONE"
        assert payload["params"] == {"file_id": "f1"}

        pubsub.unsubscribe("signal:user:99")
        pubsub.close()
        raw.close()

    def test_publish_sync_raises_when_not_initialized(self, manager):
        """Sync publish raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            manager.publish_sync("ch", "SIG")


# ==================== Idempotency ====================

@pytest.mark.asyncio
class TestIdempotency:
    """Test set_if_not_exists and exists with fakeredis."""

    async def test_set_if_not_exists_first_time_returns_true(self, async_manager):
        """First SETNX call returns True (key was set)."""
        result = await async_manager.set_if_not_exists("webhook:evt1", "processed", 60)
        assert result is True

    async def test_set_if_not_exists_duplicate_returns_false(self, async_manager):
        """Second SETNX call with same key returns False (already existed)."""
        await async_manager.set_if_not_exists("webhook:evt2", "processed", 60)
        result = await async_manager.set_if_not_exists("webhook:evt2", "processed", 60)
        assert result is False

    async def test_set_if_not_exists_different_keys_both_succeed(self, async_manager):
        """SETNX with different keys both return True."""
        r1 = await async_manager.set_if_not_exists("key:a", "v", 60)
        r2 = await async_manager.set_if_not_exists("key:b", "v", 60)
        assert r1 is True
        assert r2 is True

    async def test_set_if_not_exists_graceful_when_uninitialized(self, manager):
        """Returns True when Redis not initialized (graceful degradation)."""
        result = await manager.set_if_not_exists("key", "val", 60)
        assert result is True

    async def test_exists_returns_true_for_set_key(self, async_manager):
        """exists() returns True for a key that was set."""
        await async_manager.set_if_not_exists("mykey", "val", 60)
        assert await async_manager.exists("mykey") is True

    async def test_exists_returns_false_for_missing_key(self, async_manager):
        """exists() returns False for a key that was never set."""
        assert await async_manager.exists("no-such-key") is False

    async def test_exists_returns_false_when_uninitialized(self, manager):
        """exists() returns False when Redis not initialized (graceful degradation)."""
        assert await manager.exists("key") is False


# ==================== Distributed Lock ====================

@pytest.mark.asyncio
class TestDistributedLock:
    """Test distributed_lock with fakeredis."""

    async def test_lock_acquired_successfully(self, async_manager):
        """Lock acquisition yields True."""
        lock_cm = await async_manager.distributed_lock("test-lock", timeout_seconds=10)
        async with lock_cm as acquired:
            assert acquired is True

    async def test_lock_released_after_context_exit(self, async_manager):
        """Lock is released when context manager exits, allowing re-acquisition."""
        lock_cm = await async_manager.distributed_lock("reusable", timeout_seconds=10)
        async with lock_cm as acquired:
            assert acquired is True

        lock_cm2 = await async_manager.distributed_lock("reusable", timeout_seconds=10)
        async with lock_cm2 as acquired2:
            assert acquired2 is True

    async def test_lock_contention_yields_false(self, async_manager):
        """Second lock attempt on same name yields False while first is held."""
        lock_cm1 = await async_manager.distributed_lock("contested", timeout_seconds=10)
        async with lock_cm1 as acquired1:
            assert acquired1 is True

            lock_cm2 = await async_manager.distributed_lock("contested", timeout_seconds=10)
            async with lock_cm2 as acquired2:
                assert acquired2 is False

    async def test_lock_different_names_no_contention(self, async_manager):
        """Locks with different names don't contend with each other."""
        lock_cm1 = await async_manager.distributed_lock("lock-a", timeout_seconds=10)
        async with lock_cm1 as acquired1:
            assert acquired1 is True

            lock_cm2 = await async_manager.distributed_lock("lock-b", timeout_seconds=10)
            async with lock_cm2 as acquired2:
                assert acquired2 is True

    async def test_lock_graceful_when_uninitialized(self, manager):
        """Lock yields True when Redis not initialized (graceful degradation)."""
        lock_cm = await manager.distributed_lock("test", timeout_seconds=10)
        async with lock_cm as acquired:
            assert acquired is True


# ==================== Lifecycle ====================

@pytest.mark.asyncio
class TestAsyncLifecycle:
    """Test async initialize and shutdown."""

    async def test_shutdown_without_initialize_does_not_raise(self, manager):
        """Shutdown on uninitialized manager is a no-op."""
        await manager.shutdown()

    async def test_shutdown_after_use(self, async_manager):
        """Shutdown after Redis operations completes without error."""
        await async_manager.set_if_not_exists("k", "v", 60)
        await async_manager.shutdown()

    async def test_full_lifecycle(self, fake_server):
        """Inject, use, shutdown lifecycle works end-to-end."""
        mgr = PubSubManager(redis_url="redis://fake:6379")
        mgr._async_redis = fakeredis.FakeAsyncRedis(server=fake_server)

        result = await mgr.set_if_not_exists("lifecycle-key", "v", 60)
        assert result is True
        assert await mgr.exists("lifecycle-key") is True

        await mgr.shutdown()


class TestSyncLifecycle:
    """Test sync initialize and shutdown."""

    def test_shutdown_sync_without_initialize_does_not_raise(self, manager):
        """Sync shutdown on uninitialized manager is a no-op."""
        manager.shutdown_sync()

    def test_shutdown_sync_after_use(self, sync_manager):
        """Sync shutdown after publish completes without error."""
        sync_manager.publish_sync("ch", "EVT")
        sync_manager.shutdown_sync()
