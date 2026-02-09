"""
Unit tests for core graphql extensions module logic.

Tests ThreadSafeSessionProxy and DatabaseSessionExtension.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

from lys.core.graphql.extensions import ThreadSafeSessionProxy, DatabaseSessionExtension


class TestThreadSafeSessionProxyAsyncMethods:
    """Tests for ThreadSafeSessionProxy async methods that delegate to the real session under a lock."""

    def _run(self, coro):
        """Run a coroutine in a fresh event loop."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_scalar_delegates_to_session(self):
        session = AsyncMock()
        session.scalar.return_value = 42
        proxy = ThreadSafeSessionProxy(session)

        result = self._run(proxy.scalar("SELECT 1"))

        session.scalar.assert_awaited_once_with("SELECT 1")
        assert result == 42

    def test_scalars_delegates_to_session(self):
        session = AsyncMock()
        expected = [1, 2, 3]
        session.scalars.return_value = expected
        proxy = ThreadSafeSessionProxy(session)

        result = self._run(proxy.scalars("SELECT id FROM t"))

        session.scalars.assert_awaited_once_with("SELECT id FROM t")
        assert result == expected

    def test_stream_delegates_to_session(self):
        session = AsyncMock()
        sentinel = object()
        session.stream.return_value = sentinel
        proxy = ThreadSafeSessionProxy(session)

        result = self._run(proxy.stream("SELECT *"))

        session.stream.assert_awaited_once_with("SELECT *")
        assert result is sentinel

    def test_stream_scalars_delegates_to_session(self):
        session = AsyncMock()
        sentinel = object()
        session.stream_scalars.return_value = sentinel
        proxy = ThreadSafeSessionProxy(session)

        result = self._run(proxy.stream_scalars("SELECT id"))

        session.stream_scalars.assert_awaited_once_with("SELECT id")
        assert result is sentinel

    def test_get_delegates_to_session(self):
        session = AsyncMock()
        mock_entity = MagicMock()
        session.get.return_value = mock_entity
        proxy = ThreadSafeSessionProxy(session)

        result = self._run(proxy.get("Entity", "some-uuid"))

        session.get.assert_awaited_once_with("Entity", "some-uuid")
        assert result is mock_entity

    def test_delete_delegates_to_session(self):
        session = AsyncMock()
        instance = MagicMock()
        proxy = ThreadSafeSessionProxy(session)

        self._run(proxy.delete(instance))

        session.delete.assert_awaited_once_with(instance)

    def test_merge_delegates_to_session(self):
        session = AsyncMock()
        instance = MagicMock()
        merged = MagicMock()
        session.merge.return_value = merged
        proxy = ThreadSafeSessionProxy(session)

        result = self._run(proxy.merge(instance, load=True))

        session.merge.assert_awaited_once_with(instance, load=True)
        assert result is merged

    def test_rollback_delegates_to_session(self):
        session = AsyncMock()
        proxy = ThreadSafeSessionProxy(session)

        self._run(proxy.rollback())

        session.rollback.assert_awaited_once()


class TestThreadSafeSessionProxySyncMethods:
    """Tests for ThreadSafeSessionProxy synchronous methods."""

    def test_add_all_delegates_to_session(self):
        session = MagicMock()
        proxy = ThreadSafeSessionProxy(session)
        instances = [MagicMock(), MagicMock()]

        proxy.add_all(instances)

        session.add_all.assert_called_once_with(instances)

    def test_expunge_delegates_to_session(self):
        session = MagicMock()
        proxy = ThreadSafeSessionProxy(session)
        instance = MagicMock()

        proxy.expunge(instance)

        session.expunge.assert_called_once_with(instance)

    def test_expunge_all_delegates_to_session(self):
        session = MagicMock()
        proxy = ThreadSafeSessionProxy(session)

        proxy.expunge_all()

        session.expunge_all.assert_called_once()


class TestThreadSafeSessionProxyProperties:
    """Tests for ThreadSafeSessionProxy properties."""

    def test_is_active_delegates_to_session(self):
        session = MagicMock()
        type(session).is_active = PropertyMock(return_value=True)
        proxy = ThreadSafeSessionProxy(session)

        assert proxy.is_active is True

    def test_dirty_delegates_to_session(self):
        session = MagicMock()
        dirty_set = {"obj1", "obj2"}
        type(session).dirty = PropertyMock(return_value=dirty_set)
        proxy = ThreadSafeSessionProxy(session)

        assert proxy.dirty == dirty_set

    def test_new_delegates_to_session(self):
        session = MagicMock()
        new_set = {"new_obj"}
        type(session).new = PropertyMock(return_value=new_set)
        proxy = ThreadSafeSessionProxy(session)

        assert proxy.new == new_set

    def test_deleted_delegates_to_session(self):
        session = MagicMock()
        deleted_set = {"del_obj"}
        type(session).deleted = PropertyMock(return_value=deleted_set)
        proxy = ThreadSafeSessionProxy(session)

        assert proxy.deleted == deleted_set


class TestThreadSafeSessionProxyGetattr:
    """Tests for ThreadSafeSessionProxy __getattr__ fallback."""

    def test_getattr_falls_back_to_session(self):
        session = MagicMock()
        session.some_custom_attr = "custom_value"
        proxy = ThreadSafeSessionProxy(session)

        assert proxy.some_custom_attr == "custom_value"

    def test_getattr_method_fallback(self):
        session = MagicMock()
        session.begin_nested = MagicMock(return_value="nested_tx")
        proxy = ThreadSafeSessionProxy(session)

        result = proxy.begin_nested()

        session.begin_nested.assert_called_once()
        assert result == "nested_tx"


class TestThreadSafeSessionProxyConcurrency:
    """Tests that the lock serializes access."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_concurrent_scalar_calls_are_serialized(self):
        """Verify that concurrent calls go through the lock (no overlapping)."""
        call_order = []
        session = AsyncMock()

        async def fake_scalar(*args, **kwargs):
            call_order.append("start")
            await asyncio.sleep(0.01)
            call_order.append("end")
            return 1

        session.scalar.side_effect = fake_scalar
        proxy = ThreadSafeSessionProxy(session)

        async def run_concurrent():
            await asyncio.gather(
                proxy.scalar("q1"),
                proxy.scalar("q2"),
            )

        self._run(run_concurrent())

        # With lock serialization, we expect start-end-start-end (not start-start-end-end)
        assert call_order == ["start", "end", "start", "end"]


class TestDatabaseSessionExtensionNoAppManager:
    """Tests for DatabaseSessionExtension when app_manager is not available."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_yields_when_no_app_manager(self):
        """When context has no app_manager, extension should yield without creating a session."""
        ext = DatabaseSessionExtension.__new__(DatabaseSessionExtension)
        mock_context = MagicMock(spec=[])  # no attributes at all
        mock_exec_ctx = MagicMock()
        mock_exec_ctx.context = mock_context
        ext.execution_context = mock_exec_ctx

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())

    def test_yields_when_database_not_configured(self):
        """When app_manager exists but database is not configured, extension should yield without session."""
        ext = DatabaseSessionExtension.__new__(DatabaseSessionExtension)
        mock_app_manager = MagicMock()
        mock_app_manager.database.has_database_configured.return_value = False
        mock_context = MagicMock()
        mock_context.app_manager = mock_app_manager
        mock_exec_ctx = MagicMock()
        mock_exec_ctx.context = mock_context
        ext.execution_context = mock_exec_ctx

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())


class TestDatabaseSessionExtensionHappyPath:
    """Tests for DatabaseSessionExtension normal execution."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_extension(self):
        """Create a DatabaseSessionExtension with mocked dependencies."""
        ext = DatabaseSessionExtension.__new__(DatabaseSessionExtension)
        mock_session = AsyncMock()
        mock_app_manager = MagicMock()
        mock_app_manager.database.has_database_configured.return_value = True
        mock_app_manager.database.session_factory.return_value = mock_session
        mock_context = MagicMock()
        mock_context.app_manager = mock_app_manager
        mock_exec_ctx = MagicMock()
        mock_exec_ctx.context = mock_context
        ext.execution_context = mock_exec_ctx
        return ext, mock_session, mock_context

    def test_creates_session_and_commits_on_success(self):
        """On success, the extension should commit and close the session."""
        ext, mock_session, mock_context = self._make_extension()

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            # Verify session was set on context as a ThreadSafeSessionProxy
            assert isinstance(mock_context.session, ThreadSafeSessionProxy)
            # Signal completion (no exception)
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())

        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    def test_wraps_session_in_thread_safe_proxy(self):
        """The session stored in context should be a ThreadSafeSessionProxy."""
        ext, mock_session, mock_context = self._make_extension()

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())

        assert isinstance(mock_context.session, ThreadSafeSessionProxy)


class TestDatabaseSessionExtensionExceptionPath:
    """Tests for DatabaseSessionExtension when GraphQL execution raises."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_extension(self):
        ext = DatabaseSessionExtension.__new__(DatabaseSessionExtension)
        mock_session = AsyncMock()
        mock_app_manager = MagicMock()
        mock_app_manager.database.has_database_configured.return_value = True
        mock_app_manager.database.session_factory.return_value = mock_session
        mock_context = MagicMock()
        mock_context.app_manager = mock_app_manager
        mock_exec_ctx = MagicMock()
        mock_exec_ctx.context = mock_context
        ext.execution_context = mock_exec_ctx
        return ext, mock_session

    def test_rollback_and_reraise_on_exception(self):
        """When execution raises, extension should rollback then re-raise."""
        ext, mock_session = self._make_extension()

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(RuntimeError, match="resolver error"):
                await gen.athrow(RuntimeError("resolver error"))

        self._run(consume())

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
        # commit should NOT be called when there's an exception
        mock_session.commit.assert_not_awaited()

    def test_rollback_error_during_exception_is_suppressed(self):
        """If rollback itself fails during exception handling, the original exception is still raised."""
        ext, mock_session = self._make_extension()
        mock_session.rollback.side_effect = Exception("rollback failed")

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(RuntimeError, match="original error"):
                await gen.athrow(RuntimeError("original error"))

        self._run(consume())

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


class TestDatabaseSessionExtensionCommitFailure:
    """Tests for DatabaseSessionExtension when commit fails."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_extension(self):
        ext = DatabaseSessionExtension.__new__(DatabaseSessionExtension)
        mock_session = AsyncMock()
        mock_app_manager = MagicMock()
        mock_app_manager.database.has_database_configured.return_value = True
        mock_app_manager.database.session_factory.return_value = mock_session
        mock_context = MagicMock()
        mock_context.app_manager = mock_app_manager
        mock_exec_ctx = MagicMock()
        mock_exec_ctx.context = mock_context
        ext.execution_context = mock_exec_ctx
        return ext, mock_session

    def test_rollback_after_commit_failure(self):
        """If commit fails, the extension should rollback and close the session."""
        ext, mock_session = self._make_extension()
        mock_session.commit.side_effect = Exception("commit failed")

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    def test_rollback_failure_after_commit_failure_is_suppressed(self):
        """If both commit and rollback fail, errors are suppressed and session is still closed."""
        ext, mock_session = self._make_extension()
        mock_session.commit.side_effect = Exception("commit failed")
        mock_session.rollback.side_effect = Exception("rollback also failed")

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()


class TestDatabaseSessionExtensionCloseFailure:
    """Tests for DatabaseSessionExtension when session close fails."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _make_extension(self):
        ext = DatabaseSessionExtension.__new__(DatabaseSessionExtension)
        mock_session = AsyncMock()
        mock_app_manager = MagicMock()
        mock_app_manager.database.has_database_configured.return_value = True
        mock_app_manager.database.session_factory.return_value = mock_session
        mock_context = MagicMock()
        mock_context.app_manager = mock_app_manager
        mock_exec_ctx = MagicMock()
        mock_exec_ctx.context = mock_context
        ext.execution_context = mock_exec_ctx
        return ext, mock_session

    def test_close_failure_is_suppressed_on_success(self):
        """If session close fails after successful execution, the error is suppressed."""
        ext, mock_session = self._make_extension()
        mock_session.close.side_effect = Exception("close failed")

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            # Should not raise despite close error
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()

        self._run(consume())

        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    def test_close_failure_is_suppressed_on_exception(self):
        """If session close fails after execution error, close error is suppressed, original re-raised."""
        ext, mock_session = self._make_extension()
        mock_session.close.side_effect = Exception("close failed")

        async def consume():
            gen = ext.on_execute()
            await gen.__anext__()
            with pytest.raises(ValueError, match="exec error"):
                await gen.athrow(ValueError("exec error"))

        self._run(consume())

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
