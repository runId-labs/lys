"""
PubSubManager - Redis pub/sub manager for real-time signals.

Core infrastructure component for broadcasting messages between services.
Used by the signal app for SSE subscriptions and by any service needing
to publish real-time events.

Supports both async (HTTP server) and sync (Celery worker) operations.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Optional

import redis.asyncio as redis_async
import redis as redis_sync


class PubSubManager:
    """
    Manager for Redis pub/sub operations.

    Provides connection pooling and publish/subscribe functionality
    for both async (HTTP server) and sync (Celery worker) contexts.

    Async methods (HTTP server - FastAPI lifespan):
        - initialize(): Create async connection pool
        - shutdown(): Close async connections
        - publish(): Async publish to channel
        - subscribe(): Async subscribe to channel (SSE)

    Sync methods (Celery worker - worker_init/worker_shutdown):
        - initialize_sync(): Create sync connection pool
        - shutdown_sync(): Close sync connections
        - publish_sync(): Sync publish to channel

    Usage HTTP server:
        await app_manager.pubsub.publish("user:123", "EVENT", {"key": "value"})

    Usage Celery:
        app_manager.pubsub.publish_sync("user:123", "EVENT", {"key": "value"})
    """

    def __init__(self, redis_url: str, channel_prefix: str = "signal"):
        """
        Initialize PubSubManager.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            channel_prefix: Prefix for all channel names (default: "signal")
        """
        self.redis_url = redis_url
        self.channel_prefix = channel_prefix

        # Async client (HTTP server)
        self._async_pool: Optional[redis_async.ConnectionPool] = None
        self._async_redis: Optional[redis_async.Redis] = None

        # Sync client (Celery worker)
        self._sync_pool: Optional[redis_sync.ConnectionPool] = None
        self._sync_redis: Optional[redis_sync.Redis] = None

    def _build_channel(self, channel: str) -> str:
        """Build full channel name with prefix."""
        if self.channel_prefix:
            return f"{self.channel_prefix}:{channel}"
        return channel

    def _build_message(self, signal: str, params: dict = None) -> str:
        """Build JSON message payload."""
        return json.dumps({"signal": signal, "params": params or {}})

    # ==================== Async (HTTP server) ====================

    async def initialize(self):
        """
        Async init for FastAPI lifespan.

        Creates async connection pool for HTTP server context.
        Called automatically by AppManager._app_lifespan.
        """
        self._async_pool = redis_async.ConnectionPool.from_url(self.redis_url)
        self._async_redis = redis_async.Redis(connection_pool=self._async_pool)
        logging.info(f"PubSubManager async initialized: {self.redis_url}")

    async def shutdown(self):
        """
        Async shutdown for FastAPI lifespan.

        Closes async connections. Called automatically by AppManager._app_lifespan.
        Handles CancelledError gracefully during forced shutdown.
        """
        try:
            if self._async_redis:
                await self._async_redis.close()
            if self._async_pool:
                await self._async_pool.disconnect()
            logging.info("PubSubManager async shutdown complete")
        except asyncio.CancelledError:
            logging.warning("PubSubManager shutdown interrupted by cancellation")
        except Exception as e:
            logging.warning(f"PubSubManager shutdown error (ignored): {e}")

    async def publish(self, channel: str, signal: str, params: dict = None) -> int:
        """
        Async publish a signal to a channel.

        Args:
            channel: Channel name (will be prefixed)
            signal: Signal name (e.g., "NOTIFICATION_CREATED")
            params: Signal parameters as dict

        Returns:
            Number of subscribers that received the message

        Raises:
            RuntimeError: If async client not initialized
        """
        if not self._async_redis:
            raise RuntimeError("PubSubManager async not initialized")

        full_channel = self._build_channel(channel)
        return await self._async_redis.publish(full_channel, self._build_message(signal, params))

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """
        Async subscribe to a channel and yield messages.

        Args:
            channel: Channel name (will be prefixed)

        Yields:
            Dict with "signal" and "params" keys

        Raises:
            RuntimeError: If async client not initialized
        """
        if not self._async_redis:
            raise RuntimeError("PubSubManager async not initialized")

        full_channel = self._build_channel(channel)
        pubsub = self._async_redis.pubsub()

        try:
            await pubsub.subscribe(full_channel)
            logging.debug(f"Subscribed to channel: {full_channel}")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid JSON in channel {full_channel}: {data}")
        finally:
            await pubsub.unsubscribe(full_channel)
            await pubsub.close()
            logging.debug(f"Unsubscribed from channel: {full_channel}")

    # ==================== Sync (Celery worker) ====================

    def initialize_sync(self):
        """
        Sync init for Celery worker.

        Creates sync connection pool for Celery worker context.
        Call this in Celery worker_init signal handler.

        Example:
            @worker_init.connect
            def init_worker(**kwargs):
                if app_manager.pubsub:
                    app_manager.pubsub.initialize_sync()
        """
        self._sync_pool = redis_sync.ConnectionPool.from_url(self.redis_url)
        self._sync_redis = redis_sync.Redis(connection_pool=self._sync_pool)
        logging.info(f"PubSubManager sync initialized: {self.redis_url}")

    def shutdown_sync(self):
        """
        Sync shutdown for Celery worker.

        Closes sync connections. Call this in Celery worker_shutdown signal handler.

        Example:
            @worker_shutdown.connect
            def shutdown_worker(**kwargs):
                if app_manager.pubsub:
                    app_manager.pubsub.shutdown_sync()
        """
        if self._sync_redis:
            self._sync_redis.close()
        if self._sync_pool:
            self._sync_pool.disconnect()
        logging.info("PubSubManager sync shutdown complete")

    def publish_sync(self, channel: str, signal: str, params: dict = None) -> int:
        """
        Sync publish a signal to a channel.

        For use in Celery tasks. Requires initialize_sync() to be called first
        (typically in worker_init signal handler).

        Args:
            channel: Channel name (will be prefixed)
            signal: Signal name (e.g., "IMPORT_COMPLETED")
            params: Signal parameters as dict

        Returns:
            Number of subscribers that received the message

        Raises:
            RuntimeError: If sync client not initialized

        Example:
            @celery_app.task
            def process_import(file_id: str, user_id: str):
                # ... processing ...
                app_manager.pubsub.publish_sync(
                    channel=f"user:{user_id}",
                    signal="IMPORT_COMPLETED",
                    params={"file_id": file_id}
                )
        """
        if not self._sync_redis:
            raise RuntimeError(
                "PubSubManager sync not initialized. "
                "Call initialize_sync() in Celery worker_init signal handler."
            )

        full_channel = self._build_channel(channel)
        return self._sync_redis.publish(full_channel, self._build_message(signal, params))

    # ==================== Idempotency and Locking ====================

    async def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:
        """
        Set key only if it doesn't exist (SETNX with TTL).

        Used for webhook idempotency to ensure each event is processed once.

        Args:
            key: Redis key
            value: Value to set
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if key was set (first time), False if already existed
        """
        if not self._async_redis:
            # Graceful degradation: allow processing if Redis unavailable
            logging.warning("PubSubManager not initialized, allowing operation")
            return True

        result = await self._async_redis.set(key, value, nx=True, ex=ttl_seconds)
        return bool(result)

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis.

        Args:
            key: Redis key

        Returns:
            True if key exists
        """
        if not self._async_redis:
            return False

        return await self._async_redis.exists(key) > 0

    async def distributed_lock(self, lock_name: str, timeout_seconds: int = 30):
        """
        Acquire a distributed lock using Redis.

        Used for preventing race conditions in sync operations.

        Args:
            lock_name: Unique lock identifier
            timeout_seconds: Lock auto-release timeout

        Returns:
            Async context manager yielding True if lock acquired, False otherwise

        Usage:
            async with pubsub.distributed_lock("mollie_sync:all") as acquired:
                if acquired:
                    # Do exclusive work
        """
        import os
        import time
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _lock():
            if not self._async_redis:
                # Graceful degradation: proceed without lock
                yield True
                return

            lock_key = f"lock:{lock_name}"
            lock_value = f"{os.getpid()}:{time.time()}"

            acquired = await self._async_redis.set(
                lock_key, lock_value, nx=True, ex=timeout_seconds
            )

            try:
                yield bool(acquired)
            finally:
                if acquired:
                    # Only release if we still own the lock
                    current_value = await self._async_redis.get(lock_key)
                    if current_value and current_value.decode() == lock_value:
                        await self._async_redis.delete(lock_key)

        return _lock()