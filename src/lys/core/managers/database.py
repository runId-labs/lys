import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Dict, Any

from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, QueuePool

from lys.core.configs import DatabaseSettings

logger = logging.getLogger(__name__)


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

        # Async components
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

        # Sync components
        self._sync_engine: Optional[Engine] = None
        self._sync_session_factory: Optional[sessionmaker] = None

    def _build_url(self, async_mode: bool = True) -> str:
        """
        Build database URL from configured components.

        Args:
            async_mode: If True, use async drivers; if False, use sync drivers

        Returns:
            Database connection URL string

        Raises:
            ValueError: If database type is not supported
        """
        self.settings.validate()

        db_type = self.settings.type
        username = self.settings.username
        password = self.settings.password
        host = self.settings.host
        port = self.settings.port
        database = self.settings.database

        if db_type == "postgresql":
            driver = "asyncpg" if async_mode else "psycopg2"
            return f"postgresql+{driver}://{username}:{password}@{host}:{port}/{database}"

        elif db_type == "sqlite":
            driver = "aiosqlite" if async_mode else ""
            driver_suffix = f"+{driver}" if driver else ""
            return f"sqlite{driver_suffix}:///{database}"

        elif db_type == "mysql":
            driver = "aiomysql" if async_mode else "mysqldb"
            return f"mysql+{driver}://{username}:{password}@{host}:{port}/{database}"

        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def _get_sync_poolclass(self):
        """
        Convert async poolclass to sync equivalent.

        Returns:
            Sync pool class corresponding to configured async pool class,
            or None if no poolclass is configured
        """
        if self.settings.poolclass is None:
            return None

        # Mapping from async pools to sync equivalents
        async_to_sync_mapping = {
            AsyncAdaptedQueuePool: QueuePool,
        }

        return async_to_sync_mapping.get(
            self.settings.poolclass,
            self.settings.poolclass  # Return as-is if already sync or unknown
        )

    def _get_engine_kwargs(self, async_mode: bool = True) -> Dict[str, Any]:
        """
        Get keyword arguments for engine creation.

        Args:
            async_mode: If True, configure for async engine; if False, for sync engine

        Returns:
            Dict with engine configuration parameters
        """
        self.settings.validate()

        kwargs: Dict[str, Any] = {
            "pool_pre_ping": self.settings.pool_pre_ping,
            "pool_recycle": self.settings.pool_recycle,
            "echo": self.settings.echo,
            "echo_pool": self.settings.echo_pool,
        }

        # Poolclass
        if async_mode:
            if self.settings.poolclass is not None:
                kwargs["poolclass"] = self.settings.poolclass
        else:
            sync_poolclass = self._get_sync_poolclass()
            if sync_poolclass is not None:
                kwargs["poolclass"] = sync_poolclass

        # Pool size settings
        if self.settings.pool_size is not None:
            kwargs["pool_size"] = self.settings.pool_size

        if self.settings.max_overflow is not None:
            kwargs["max_overflow"] = self.settings.max_overflow

        # Build connect_args with SSL configuration
        connect_args = dict(self.settings.connect_args) if self.settings.connect_args else {}

        if self.settings.type == "postgresql":
            if self.settings.ssl_mode:
                # asyncpg uses "ssl", psycopg2 uses "sslmode"
                ssl_key = "ssl" if async_mode else "sslmode"
                connect_args.setdefault(ssl_key, self.settings.ssl_mode)
            else:
                logger.warning(
                    "PostgreSQL connection without SSL (ssl_mode is disabled). "
                    "Set database.ssl_mode = 'require' for production environments."
                )

        if connect_args:
            kwargs["connect_args"] = connect_args

        return kwargs

    def create_database_engine(self) -> AsyncEngine:
        """
        Create async database engine using configured settings.

        Returns:
            AsyncEngine instance configured with current settings

        Raises:
            ValueError: If database settings are not configured
        """
        url = self._build_url(async_mode=True)
        engine_kwargs = self._get_engine_kwargs(async_mode=True)
        return create_async_engine(url, **engine_kwargs)

    def create_sync_database_engine(self) -> Engine:
        """
        Create sync database engine using configured settings.

        Returns:
            Engine instance configured with current settings

        Raises:
            ValueError: If database settings are not configured
        """
        url = self._build_url(async_mode=False)
        engine_kwargs = self._get_engine_kwargs(async_mode=False)
        return create_engine(url, **engine_kwargs)

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

    def get_sync_engine(self) -> Engine:
        """
        Get the global sync database engine instance.

        Creates the engine on first access using configured settings.

        Returns:
            Engine instance

        Raises:
            ValueError: If database settings are not configured
        """
        if self._sync_engine is None:
            self._sync_engine = self.create_sync_database_engine()
        return self._sync_engine

    def get_session_factory(self) -> async_sessionmaker:
        """
        Get the global async session factory.

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

    def get_sync_session_factory(self) -> sessionmaker:
        """
        Get the global sync session factory.

        Creates the factory on first access using the current sync engine.

        Returns:
            sessionmaker instance
        """
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                self.get_sync_engine(),
                class_=Session,
                expire_on_commit=False
            )
        return self._sync_session_factory

    def reset_database_connection(self):
        """
        Reset database connections.

        This forces recreation of engine and session factory on next access.
        Useful when changing database configuration at runtime.
        """
        # Reset async components
        if self._engine:
            pass  # Dispose is handled by close() method
        self._engine = None
        self._session_factory = None

        # Reset sync components
        if self._sync_engine:
            self._sync_engine.dispose()
        self._sync_engine = None
        self._sync_session_factory = None

    def has_database_configured(self):
        return self.settings.configured()

    @property
    def engine(self) -> AsyncEngine:
        """Get the async database engine."""
        return self.get_engine()

    @property
    def sync_engine(self) -> Engine:
        """Get the sync database engine."""
        return self.get_sync_engine()

    @property
    def session_factory(self) -> async_sessionmaker:
        """Get the async session factory."""
        return self.get_session_factory()

    @property
    def sync_session_factory(self) -> sessionmaker:
        """Get the sync session factory."""
        return self.get_sync_session_factory()

    @asynccontextmanager
    async def get_session(self):
        """
        Context manager for obtaining an async database session.
        Automatically handles commit/rollback.
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

    @contextmanager
    def get_sync_session(self):
        """
        Context manager for obtaining a sync database session.
        Automatically handles commit/rollback.
        """
        session = self.sync_session_factory()
        try:
            yield session
            session.commit()
        except NonBlockingRollbackException:
            session.rollback()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_session(self) -> AsyncSession:
        """Create a new async session."""
        return self.session_factory()

    def create_sync_session(self) -> Session:
        """Create a new sync session."""
        return self.sync_session_factory()

    async def execute_parallel(self, *queries):
        """
            results = await db.execute_parallel(
                lambda s: s.execute(select(User)),
                lambda s: s.execute(select(Client)),
                lambda s: s.execute(select(UserStatus))
            )
        """
        async def execute_with_session(query_func):
            async with self.get_session() as session:
                return await query_func(session)

        # Exécute toutes les requêtes en parallèle
        tasks = [execute_with_session(query_func) for query_func in queries]
        return await asyncio.gather(*tasks)

    async def close(self):
        """
        Close database connections and dispose of the engine.
        """
        if self._engine:
            await self._engine.dispose()
        self.reset_database_connection()
