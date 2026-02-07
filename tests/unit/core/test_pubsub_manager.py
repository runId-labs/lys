"""
Unit tests for PubSubManager.
"""
import inspect


class TestPubSubManagerStructure:
    """Tests for PubSubManager class structure."""

    def test_manager_exists(self):
        from lys.core.managers.pubsub import PubSubManager
        assert PubSubManager is not None

    def test_constructor_accepts_redis_url(self):
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379")
        assert manager.redis_url == "redis://localhost:6379"

    def test_constructor_default_channel_prefix(self):
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379")
        assert manager.channel_prefix == "signal"

    def test_constructor_custom_channel_prefix(self):
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379", channel_prefix="custom")
        assert manager.channel_prefix == "custom"

    def test_has_publish_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "publish")
        assert inspect.iscoroutinefunction(PubSubManager.publish)

    def test_has_subscribe_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "subscribe")
        assert inspect.isasyncgenfunction(PubSubManager.subscribe)

    def test_has_set_if_not_exists_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "set_if_not_exists")
        assert inspect.iscoroutinefunction(PubSubManager.set_if_not_exists)

    def test_has_exists_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "exists")
        assert inspect.iscoroutinefunction(PubSubManager.exists)

    def test_has_shutdown_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "shutdown")
        assert inspect.iscoroutinefunction(PubSubManager.shutdown)

    def test_has_initialize_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "initialize")
        assert inspect.iscoroutinefunction(PubSubManager.initialize)

    def test_has_publish_sync_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "publish_sync")
        assert callable(PubSubManager.publish_sync)

    def test_has_initialize_sync_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "initialize_sync")
        assert callable(PubSubManager.initialize_sync)

    def test_has_shutdown_sync_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "shutdown_sync")
        assert callable(PubSubManager.shutdown_sync)

    def test_has_distributed_lock_method(self):
        from lys.core.managers.pubsub import PubSubManager
        assert hasattr(PubSubManager, "distributed_lock")
        assert inspect.iscoroutinefunction(PubSubManager.distributed_lock)


class TestPubSubManagerChannelBuilding:
    """Tests for channel and message building helpers."""

    def test_build_channel_with_prefix(self):
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379", channel_prefix="signal")
        assert manager._build_channel("user:123") == "signal:user:123"

    def test_build_channel_without_prefix(self):
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379", channel_prefix="")
        assert manager._build_channel("user:123") == "user:123"

    def test_build_message_with_params(self):
        import json
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379")
        msg = json.loads(manager._build_message("EVENT", {"key": "value"}))
        assert msg["signal"] == "EVENT"
        assert msg["params"] == {"key": "value"}

    def test_build_message_without_params(self):
        import json
        from lys.core.managers.pubsub import PubSubManager
        manager = PubSubManager(redis_url="redis://localhost:6379")
        msg = json.loads(manager._build_message("EVENT"))
        assert msg["signal"] == "EVENT"
        assert msg["params"] == {}
