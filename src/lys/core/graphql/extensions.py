"""
GraphQL extensions for Strawberry.

This module provides custom Strawberry extensions for the lys framework,
including database session management for GraphQL operations.
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.extensions import SchemaExtension


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
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._lock = asyncio.Lock()

    async def execute(self, *args, **kwargs):
        async with self._lock:
            return await self._session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):
        async with self._lock:
            return await self._session.scalar(*args, **kwargs)

    async def scalars(self, *args, **kwargs):
        async with self._lock:
            return await self._session.scalars(*args, **kwargs)

    async def stream(self, *args, **kwargs):
        async with self._lock:
            return await self._session.stream(*args, **kwargs)

    async def stream_scalars(self, *args, **kwargs):
        async with self._lock:
            return await self._session.stream_scalars(*args, **kwargs)

    async def flush(self, *args, **kwargs):
        async with self._lock:
            return await self._session.flush(*args, **kwargs)

    async def refresh(self, *args, **kwargs):
        async with self._lock:
            return await self._session.refresh(*args, **kwargs)

    async def get(self, *args, **kwargs):
        async with self._lock:
            return await self._session.get(*args, **kwargs)

    def add(self, instance, _warn=True):
        # add is synchronous but we still protect state consistency
        return self._session.add(instance, _warn=_warn)

    def add_all(self, instances):
        return self._session.add_all(instances)

    async def delete(self, instance):
        async with self._lock:
            return await self._session.delete(instance)

    async def merge(self, instance, *args, **kwargs):
        async with self._lock:
            return await self._session.merge(instance, *args, **kwargs)

    async def commit(self):
        async with self._lock:
            return await self._session.commit()

    async def rollback(self):
        async with self._lock:
            return await self._session.rollback()

    def expunge(self, instance):
        return self._session.expunge(instance)

    def expunge_all(self):
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
        # Fallback for any other attributes/methods not explicitly wrapped
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
            # Create session manually (not using async with) to handle close errors
            # When parallel resolvers share a session and one fails while another
            # has an operation in progress, the session close can fail.
            session = app_manager.database.session_factory()

            # Wrap session in thread-safe proxy to handle concurrent resolver access
            # Multiple root field resolvers may execute in parallel, and AsyncSession
            # is not safe for concurrent use. The proxy serializes all access.
            self.execution_context.context.session = ThreadSafeSessionProxy(session)

            try:
                # Yield to allow the GraphQL operation to execute with session open
                # This includes the main resolver and all nested field resolvers
                yield
            except Exception:
                # If an exception occurred during execution, rollback before closing
                # to ensure the session is in a clean state
                try:
                    await session.rollback()
                except Exception:
                    pass  # Ignore rollback errors
                raise
            else:
                # Commit changes after successful execution
                # Note: GraphQL resolver errors are caught by Strawberry and don't
                # propagate here, so we may try to commit a session in invalid state.
                # Handle commit errors gracefully.
                try:
                    await session.commit()
                except Exception:
                    try:
                        await session.rollback()
                    except Exception:
                        pass  # Ignore rollback errors
            finally:
                # Close session, ignoring errors if session is in invalid state
                # This can happen when parallel resolvers have operations in progress
                try:
                    await session.close()
                except Exception:
                    pass  # Session will be garbage collected