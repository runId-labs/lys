"""
Unit tests for DatabaseManager logic (_build_url, _get_sync_poolclass, _get_engine_kwargs, etc.).
"""
import pytest

from sqlalchemy.pool import AsyncAdaptedQueuePool, QueuePool, NullPool

from lys.core.configs import DatabaseSettings
from lys.core.managers.database import DatabaseManager


class TestBuildUrl:
    """Tests for DatabaseManager._build_url()."""

    def _make_manager(self, **overrides):
        settings = DatabaseSettings()
        for k, v in overrides.items():
            setattr(settings, k, v)
        return DatabaseManager(settings)

    def test_postgresql_async(self):
        mgr = self._make_manager(
            type="postgresql", host="db.host", port=5432,
            username="user", password="pass", database="mydb"
        )
        url = mgr._build_url(async_mode=True)
        assert url == "postgresql+asyncpg://user:pass@db.host:5432/mydb"

    def test_postgresql_sync(self):
        mgr = self._make_manager(
            type="postgresql", host="db.host", port=5432,
            username="user", password="pass", database="mydb"
        )
        url = mgr._build_url(async_mode=False)
        assert url == "postgresql+psycopg2://user:pass@db.host:5432/mydb"

    def test_sqlite_async(self):
        mgr = self._make_manager(type="sqlite", database=":memory:")
        url = mgr._build_url(async_mode=True)
        assert url == "sqlite+aiosqlite:///:memory:"

    def test_sqlite_sync(self):
        mgr = self._make_manager(type="sqlite", database=":memory:")
        url = mgr._build_url(async_mode=False)
        assert url == "sqlite:///:memory:"

    def test_mysql_async(self):
        mgr = self._make_manager(
            type="mysql", host="db.host", port=3306,
            username="user", password="pass", database="mydb"
        )
        url = mgr._build_url(async_mode=True)
        assert url == "mysql+aiomysql://user:pass@db.host:3306/mydb"

    def test_unsupported_type_raises(self):
        mgr = self._make_manager(
            type="oracle", host="db.host", port=1521,
            username="user", password="pass", database="mydb"
        )
        with pytest.raises(ValueError, match="Unsupported database type: oracle"):
            mgr._build_url()


class TestGetSyncPoolclass:
    """Tests for DatabaseManager._get_sync_poolclass()."""

    def test_none_returns_none(self):
        settings = DatabaseSettings()
        settings.poolclass = None
        mgr = DatabaseManager(settings)
        assert mgr._get_sync_poolclass() is None

    def test_async_adapted_maps_to_queue_pool(self):
        settings = DatabaseSettings()
        settings.poolclass = AsyncAdaptedQueuePool
        mgr = DatabaseManager(settings)
        assert mgr._get_sync_poolclass() is QueuePool

    def test_unknown_pool_returns_as_is(self):
        settings = DatabaseSettings()
        settings.poolclass = NullPool
        mgr = DatabaseManager(settings)
        assert mgr._get_sync_poolclass() is NullPool


class TestGetEngineKwargs:
    """Tests for DatabaseManager._get_engine_kwargs()."""

    def _make_manager(self, **overrides):
        settings = DatabaseSettings()
        settings.type = "sqlite"
        settings.database = ":memory:"
        for k, v in overrides.items():
            setattr(settings, k, v)
        return DatabaseManager(settings)

    def test_includes_pool_pre_ping(self):
        mgr = self._make_manager()
        kwargs = mgr._get_engine_kwargs()
        assert "pool_pre_ping" in kwargs

    def test_pool_size_included_when_set(self):
        mgr = self._make_manager(pool_size=10)
        kwargs = mgr._get_engine_kwargs()
        assert kwargs["pool_size"] == 10

    def test_pool_size_excluded_when_none(self):
        mgr = self._make_manager()
        kwargs = mgr._get_engine_kwargs()
        assert "pool_size" not in kwargs

    def test_connect_args_included_when_set(self):
        mgr = self._make_manager(connect_args={"check_same_thread": False})
        kwargs = mgr._get_engine_kwargs()
        assert kwargs["connect_args"] == {"check_same_thread": False}

    def test_connect_args_excluded_when_empty(self):
        mgr = self._make_manager()
        kwargs = mgr._get_engine_kwargs()
        assert "connect_args" not in kwargs

    def test_async_poolclass_used_in_async_mode(self):
        mgr = self._make_manager(poolclass=AsyncAdaptedQueuePool)
        kwargs = mgr._get_engine_kwargs(async_mode=True)
        assert kwargs["poolclass"] is AsyncAdaptedQueuePool

    def test_sync_poolclass_used_in_sync_mode(self):
        mgr = self._make_manager(poolclass=AsyncAdaptedQueuePool)
        kwargs = mgr._get_engine_kwargs(async_mode=False)
        assert kwargs["poolclass"] is QueuePool

    def test_max_overflow_included_when_set(self):
        mgr = self._make_manager(max_overflow=20)
        kwargs = mgr._get_engine_kwargs()
        assert kwargs["max_overflow"] == 20


class TestResetAndHasDatabase:
    """Tests for reset_database_connection() and has_database_configured()."""

    def test_has_database_configured_false_by_default(self):
        settings = DatabaseSettings()
        mgr = DatabaseManager(settings)
        assert mgr.has_database_configured() is False

    def test_has_database_configured_true_when_type_set(self):
        settings = DatabaseSettings()
        settings.type = "sqlite"
        mgr = DatabaseManager(settings)
        assert mgr.has_database_configured() is True

    def test_reset_clears_engine_and_factory(self):
        settings = DatabaseSettings()
        settings.type = "sqlite"
        settings.database = ":memory:"
        mgr = DatabaseManager(settings)
        # Simulate state
        mgr._engine = "fake_engine"
        mgr._session_factory = "fake_factory"
        mgr._sync_engine = None
        mgr._sync_session_factory = None
        mgr.reset_database_connection()
        assert mgr._engine is None
        assert mgr._session_factory is None
        assert mgr._sync_engine is None
        assert mgr._sync_session_factory is None
