from contextlib import asynccontextmanager
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from lys.core.configs import DatabaseSettings


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    This base class provides the foundation for all database entities
    in the lys framework.
    """
    __table_args__ = {'extend_existing': True}
    __abstract__ = True


class NonBlockingRollbackException(Exception):
    pass


class DatabaseManager:
    """
    Database manager providing high-level database operations.

    This class provides convenient methods for database operations
    and automatically uses the configured database settings.
    """


    def __init__(self, settings: DatabaseSettings):
        self.settings = settings

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

    def create_database_engine(self) -> AsyncEngine:
        """
        Create database engine using configured settings.

        Returns:
            AsyncEngine instance configured with current settings

        Raises:
            ValueError: If database settings are not configured
        """
        engine_kwargs = self.settings.get_engine_kwargs()
        return create_async_engine(self.settings.url, **engine_kwargs)

    def get_engine(self) -> AsyncEngine:
        """
        Get the global database engine instance.

        Creates the engine on first access using configured settings.

        Returns:
            AsyncEngine instance

        Raises:
            ValueError: If database settings are not configured
        """
        if self._engine is None:
            self._engine = self.create_database_engine()
        return self._engine

    def get_session_factory(self) -> async_sessionmaker:
        """
        Get the global session factory.

        Creates the factory on first access using the current engine.

        Returns:
            async_sessionmaker instance
        """
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False
            )
        return self._session_factory

    def reset_database_connection(self):
        """
        Reset database connections.

        This forces recreation of engine and session factory on next access.
        Useful when changing database configuration at runtime.
        """
        if self._engine:
            # Note: In a real app, you might want to properly dispose the engine
            pass
        self._engine = None
        self._session_factory = None

    def has_database_configured(self):
        return self.settings.configured() is not None

    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine."""
        return self.get_engine()

    @property
    def session_factory(self) -> async_sessionmaker:
        """Get the session factory."""
        return self.get_session_factory()

    @asynccontextmanager
    async def get_session(self):
        """
        Context manager pour obtenir une session DB
        Gère automatiquement commit/rollback
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except NonBlockingRollbackException:
                await session.rollback()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def create_session(self) -> AsyncSession:
        return self.session_factory()

    async def execute_parallel(self, *queries):
        """
            results = await db.execute_parallel(
                lambda s: s.execute(select(User)),
                lambda s: s.execute(select(Client)),
                lambda s: s.execute(select(UserStatus))
            )
        """
        import asyncio

        async def execute_with_session(query_func):
            async with self.get_session() as session:
                return await query_func(session)

        # Exécute toutes les requêtes en parallèle
        tasks = [execute_with_session(query_func) for query_func in queries]
        return await asyncio.gather(*tasks)

    async def initialize_database(self):
        """
        Initialize database by creating all tables.

        This method creates all tables defined in the Base metadata.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self):
        """
        Close database connections and dispose of the engine.
        """
        if self._engine:
            await self._engine.dispose()
        self.reset_database_connection()
