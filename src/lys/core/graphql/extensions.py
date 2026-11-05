"""
GraphQL extensions for Strawberry.

This module provides custom Strawberry extensions for the lys framework,
including database session management for GraphQL operations.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.extensions import SchemaExtension

logger = logging.getLogger(__name__)


class _MaterializedAsyncResult:
    """
    Async-iterable wrapper over an already-materialized list of results.

    Used by ThreadSafeSessionProxy to replace stream/stream_scalars cursors
    with pre-fetched data, so the asyncpg connection is freed before the
    lock is released.
    """

    def __init__(self, items: list):
        self._iter = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class ThreadSafeSessionProxy:
    """
    Proxy that serializes all access to an AsyncSession.

    SQLAlchemy's AsyncSession is not thread-safe and cannot be used concurrently
    by multiple coroutines. In GraphQL, multiple root field resolvers may execute
    in parallel, all sharing the same session from the context.

    This proxy wraps the session and uses an asyncio.Lock to ensure only one
    coroutine accesses the session at a time, preventing race conditions.

    Usage:
        The proxy is transparent to resolvers - they continue using
        info.context.session as before, but all operations are now serialized.

    The same lock guards the end of the session (see :meth:`end`): a resolver can still be
    running when the operation is over - graphql-core abandons, without cancelling, the
    sibling fields of a non-null field that failed - and its query must finish before the
    session's connection is released.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._lock = asyncio.Lock()
        self._ended = False

    def _ensure_open(self) -> None:
        """Refuse any use of the session once it has ended."""
        if self._ended:
            raise RuntimeError("The session of this GraphQL operation has ended")

    @asynccontextmanager
    async def _use(self):
        """Hold the session for one operation; refused once the session has ended."""
        async with self._lock:
            self._ensure_open()
            yield

    async def end(self, commit: bool) -> None:
        """
        Commit or roll back, then release the connection - once no resolver is using it.

        A connection whose state is unknown after a failure is invalidated rather than
        returned to the pool: back in the pool, it fails the next request that checks it out,
        whoever that request belongs to.
        """
        async with self._lock:
            self._ended = True
            if not await self._settle(commit):
                await self._invalidate()
                return
            try:
                await self._session.close()
            except Exception:
                logger.warning("Session close failed, invalidating its connection", exc_info=True)
                await self._invalidate()

    async def _settle(self, commit: bool) -> bool:
        """Commit (falling back to a rollback) or roll back; whether the transaction ended cleanly."""
        if commit:
            try:
                await self._session.commit()
                return True
            except Exception:
                # Expected after a resolver error left the session unusable: Strawberry
                # catches resolver errors, so the operation still ends on the success path.
                logger.debug("Session commit failed, rolling back", exc_info=True)
        try:
            await self._session.rollback()
            return True
        except Exception:
            logger.warning("Session rollback failed", exc_info=True)
            return False

    async def _invalidate(self) -> None:
        try:
            await self._session.invalidate()
        except Exception:
            logger.warning("Session invalidation failed", exc_info=True)

    async def execute(self, *args, **kwargs):
        async with self._use():
            return await self._session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):
        async with self._use():
            return await self._session.scalar(*args, **kwargs)

    async def scalars(self, *args, **kwargs):
        async with self._use():
            return await self._session.scalars(*args, **kwargs)

    async def stream(self, *args, **kwargs):
        async with self._use():
            result = await self._session.stream(*args, **kwargs)
            # Materialize all rows while holding the lock.
            # stream() returns a cursor that keeps the asyncpg connection busy
            # until fully consumed. Releasing the lock before consumption would
            # cause "another operation is in progress" errors for concurrent resolvers.
            rows = [row async for row in result]
        return _MaterializedAsyncResult(rows)

    async def stream_scalars(self, *args, **kwargs):
        async with self._use():
            result = await self._session.stream_scalars(*args, **kwargs)
            # Materialize all scalars while holding the lock.
            # stream_scalars() returns a cursor that keeps the asyncpg connection busy
            # until fully consumed. Releasing the lock before consumption would
            # cause "another operation is in progress" errors for concurrent resolvers.
            items = [item async for item in result]
        return _MaterializedAsyncResult(items)

    async def flush(self, *args, **kwargs):
        async with self._use():
            return await self._session.flush(*args, **kwargs)

    async def refresh(self, *args, **kwargs):
        async with self._use():
            return await self._session.refresh(*args, **kwargs)

    async def get(self, *args, **kwargs):
        async with self._use():
            return await self._session.get(*args, **kwargs)

    # The synchronous methods issue no query and need no lock, but are refused once the
    # session has ended: an instance added then would be silently dropped.
    def add(self, instance, _warn=True):
        self._ensure_open()
        return self._session.add(instance, _warn=_warn)

    def add_all(self, instances):
        self._ensure_open()
        return self._session.add_all(instances)

    async def delete(self, instance):
        async with self._use():
            return await self._session.delete(instance)

    async def merge(self, instance, *args, **kwargs):
        async with self._use():
            return await self._session.merge(instance, *args, **kwargs)

    async def commit(self):
        async with self._use():
            return await self._session.commit()

    async def rollback(self):
        async with self._use():
            return await self._session.rollback()

    def expunge(self, instance):
        self._ensure_open()
        return self._session.expunge(instance)

    def expunge_all(self):
        self._ensure_open()
        return self._session.expunge_all()

    @property
    def is_active(self):
        return self._session.is_active

    @property
    def dirty(self):
        return self._session.dirty

    @property
    def new(self):
        return self._session.new

    @property
    def deleted(self):
        return self._session.deleted

    def __getattr__(self, name):
        # Fallback for any other attributes/methods not explicitly wrapped. Dunder lookups
        # (copy, pickle, introspection probes) keep their AttributeError semantics.
        if not name.startswith("__"):
            self._ensure_open()
        return getattr(self._session, name)


class DatabaseSessionExtension(SchemaExtension):
    """
    Strawberry extension that manages database session lifecycle for GraphQL operations.

    This extension opens a database session at the start of a GraphQL request and keeps it
    open for the entire duration of the GraphQL resolution (including nested field resolvers).
    The session is automatically closed when the GraphQL operation completes.

    Benefits:
    - Eliminates DetachedInstanceError by keeping entities attached during resolution
    - Allows lazy loading of relationships without explicit eager loading
    - Follows standard GraphQL/Strawberry patterns for database session management
    - Simplifies resolver code by removing need for manual session management

    Trade-offs:
    - Sessions remain open longer (entire GraphQL operation vs. per-resolver)
    - Potential N+1 query problem if lazy loading is used extensively
    - Recommend using dataloaders for frequently accessed relationships

    Usage:
        The extension is automatically configured in the schema and requires no
        changes to resolver code. Resolvers access the session via info.context.session.
    """

    async def on_execute(self):
        """
        Hook called at the start of GraphQL execution.

        Opens a database session, stores it in the GraphQL context, executes the
        entire GraphQL operation (including all nested resolvers), and then closes
        the session.

        Yields control to allow the GraphQL operation to execute, then cleans up.
        """
        # Get app_manager from context (set by get_context or resolver)
        app_manager = getattr(self.execution_context.context, "app_manager", None)

        # If no app_manager in context yet, we'll let individual resolvers handle sessions
        # This can happen for introspection queries or before resolvers set app_manager
        # Also skip if database is not configured (e.g., stateless services like signal-api)
        if app_manager is None or not app_manager.database.has_database_configured():
            yield

        else:
            session = app_manager.database.session_factory()

            # Wrap session in thread-safe proxy to handle concurrent resolver access
            # Multiple root field resolvers may execute in parallel, and AsyncSession
            # is not safe for concurrent use. The proxy serializes all access.
            proxy = ThreadSafeSessionProxy(session)
            self.execution_context.context.session = proxy

            try:
                # Yield to allow the GraphQL operation to execute with session open
                # This includes the main resolver and all nested field resolvers
                yield
            except BaseException:
                # BaseException, not Exception: a cancelled operation (timeout, closed
                # socket) must release its connection too. Shielded so that a second
                # cancellation cannot interrupt the release halfway.
                await asyncio.shield(proxy.end(commit=False))
                raise
            else:
                # GraphQL resolver errors are caught by Strawberry and do not propagate
                # here, so a session left unusable by one still ends on this path: end()
                # falls back to a rollback when the commit fails.
                await proxy.end(commit=True)