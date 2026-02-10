"""
Unit tests for core configuration logic (validation, properties, methods).
"""
import pytest

from lys.core.configs import DatabaseSettings, AppSettings, CelerySettings, EmailSettings, AISettings
from lys.core.consts.environments import EnvironmentEnum


class TestDatabaseSettingsValidation:
    """Tests for DatabaseSettings.validate() logic."""

    def test_validate_raises_when_type_is_none(self):
        db = DatabaseSettings()
        with pytest.raises(ValueError, match="Database must be configured"):
            db.validate()

    def test_validate_sqlite_without_database_raises(self):
        db = DatabaseSettings()
        db.type = "sqlite"
        db.database = None
        with pytest.raises(ValueError, match="SQLite requires 'database' parameter"):
            db.validate()

    def test_validate_sqlite_with_database_passes(self):
        db = DatabaseSettings()
        db.type = "sqlite"
        db.database = ":memory:"
        db.validate()

    def test_validate_postgresql_missing_host(self):
        db = DatabaseSettings()
        db.type = "postgresql"
        db.port = 5432
        db.username = "user"
        db.password = "pass"
        db.database = "mydb"
        with pytest.raises(ValueError, match="host"):
            db.validate()

    def test_validate_postgresql_complete_passes(self):
        db = DatabaseSettings()
        db.type = "postgresql"
        db.host = "localhost"
        db.port = 5432
        db.username = "user"
        db.password = "pass"
        db.database = "mydb"
        db.validate()

    def test_validate_unsupported_type_raises(self):
        db = DatabaseSettings()
        db.type = "oracle"
        with pytest.raises(ValueError, match="Unsupported database type: oracle"):
            db.validate()


class TestAppSettingsProperties:
    """Tests for AppSettings environment-driven properties."""

    def test_debug_true_for_dev(self):
        app = AppSettings()
        app.env = EnvironmentEnum.DEV
        assert app.debug is True

    def test_debug_false_for_demo(self):
        app = AppSettings()
        app.env = EnvironmentEnum.DEMO
        assert app.debug is False

    def test_debug_false_for_preprod(self):
        app = AppSettings()
        app.env = EnvironmentEnum.PREPROD
        assert app.debug is False

    def test_debug_false_for_prod(self):
        app = AppSettings()
        app.env = EnvironmentEnum.PROD
        assert app.debug is False

    def test_testing_true_only_for_dev(self):
        app = AppSettings()
        app.env = EnvironmentEnum.DEV
        assert app.testing is True

    def test_testing_false_for_prod(self):
        app = AppSettings()
        app.env = EnvironmentEnum.PROD
        assert app.testing is False

    def test_log_level_dev(self):
        app = AppSettings()
        app.env = EnvironmentEnum.DEV
        assert app.log_level == "DEBUG"

    def test_log_level_demo(self):
        app = AppSettings()
        app.env = EnvironmentEnum.DEMO
        assert app.log_level == "INFO"

    def test_log_level_preprod(self):
        app = AppSettings()
        app.env = EnvironmentEnum.PREPROD
        assert app.log_level == "WARNING"

    def test_log_level_prod(self):
        app = AppSettings()
        app.env = EnvironmentEnum.PROD
        assert app.log_level == "ERROR"


class TestAppSettingsMethods:
    """Tests for AppSettings add/remove/configure methods."""

    def test_add_app_adds_new(self):
        app = AppSettings()
        app.add_app("lys.apps.base")
        assert "lys.apps.base" in app.apps

    def test_add_app_idempotent(self):
        app = AppSettings()
        app.add_app("lys.apps.base")
        app.add_app("lys.apps.base")
        assert app.apps.count("lys.apps.base") == 1

    def test_remove_app(self):
        app = AppSettings()
        app.add_app("lys.apps.base")
        app.remove_app("lys.apps.base")
        assert "lys.apps.base" not in app.apps

    def test_remove_app_not_present_is_noop(self):
        app = AppSettings()
        app.remove_app("nonexistent")
        assert app.apps == []

    def test_add_middleware(self):
        app = AppSettings()
        app.add_middleware("lys.middleware.cors")
        assert "lys.middleware.cors" in app.middlewares

    def test_add_middleware_idempotent(self):
        app = AppSettings()
        app.add_middleware("lys.middleware.cors")
        app.add_middleware("lys.middleware.cors")
        assert app.middlewares.count("lys.middleware.cors") == 1

    def test_configure_plugin(self):
        app = AppSettings()
        app.configure_plugin("redis", url="redis://localhost:6379")
        assert app.get_plugin_config("redis") == {"url": "redis://localhost:6379"}

    def test_get_plugin_config_missing_returns_empty(self):
        app = AppSettings()
        assert app.get_plugin_config("nonexistent") == {}

    def test_configure_raises_on_unknown_setting(self):
        app = AppSettings()
        with pytest.raises(ValueError, match="Unknown app setting"):
            app.configure(nonexistent_setting="value")


class TestBaseSettingsConfigure:
    """Tests for BaseSettings.configure method."""

    def test_configure_sets_known_attributes(self):
        db = DatabaseSettings()
        db.configure(type="sqlite", database=":memory:")
        assert db.type == "sqlite"
        assert db.database == ":memory:"

    def test_configure_raises_on_unknown_key(self):
        db = DatabaseSettings()
        with pytest.raises(ValueError, match="Unknown DatabaseSettings setting"):
            db.configure(unknown_key="value")


class TestCelerySettingsValidation:
    """Tests for CelerySettings.validate() logic."""

    def test_validate_passes_with_defaults(self):
        celery = CelerySettings()
        celery.validate()

    def test_validate_raises_without_broker(self):
        celery = CelerySettings()
        celery.broker_url = ""
        with pytest.raises(ValueError, match="Celery broker_url must be configured"):
            celery.validate()


class TestEmailSettingsValidation:
    """Tests for EmailSettings.validate() logic."""

    def test_validate_raises_without_sender(self):
        email = EmailSettings()
        with pytest.raises(ValueError, match="Email sender must be configured"):
            email.validate()

    def test_configured_returns_false_without_sender(self):
        email = EmailSettings()
        assert email.configured() is False

    def test_configured_returns_true_with_sender(self):
        email = EmailSettings()
        email.sender = "test@example.com"
        assert email.configured() is True


class TestAISettingsValidation:
    """Tests for AISettings.validate() and configured() logic."""

    def test_validate_raises_when_enabled_without_api_key(self):
        ai = AISettings()
        ai.enabled = True
        with pytest.raises(ValueError, match="AI is enabled but api_key is not configured"):
            ai.validate()

    def test_validate_passes_when_disabled(self):
        ai = AISettings()
        ai.enabled = False
        ai.validate()

    def test_configured_returns_true(self):
        ai = AISettings()
        ai.enabled = True
        ai.api_key = "test-key"
        assert ai.configured() is True

    def test_configured_returns_false_when_disabled(self):
        ai = AISettings()
        ai.enabled = False
        ai.api_key = "test-key"
        assert ai.configured() is False

    def test_clear_routes_cache(self):
        ai = AISettings()
        ai._routes_manifest_cache = {"some": "data"}
        ai.clear_routes_cache()
        assert ai._routes_manifest_cache is None

    def test_get_routes_manifest_returns_none_without_path(self):
        ai = AISettings()
        assert ai.get_routes_manifest() is None

    def test_get_routes_manifest_returns_cache(self):
        ai = AISettings()
        ai._routes_manifest_cache = {"cached": True}
        assert ai.get_routes_manifest() == {"cached": True}
