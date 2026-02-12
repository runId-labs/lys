"""
Unit tests for core configuration classes.
"""


class TestBaseSettings:
    """Tests for BaseSettings class."""

    def test_class_exists(self):
        from lys.core.configs import BaseSettings
        assert BaseSettings is not None

    def test_has_configure_method(self):
        from lys.core.configs import BaseSettings
        assert hasattr(BaseSettings, "configure")


class TestDatabaseSettings:
    """Tests for DatabaseSettings class."""

    def test_class_exists(self):
        from lys.core.configs import DatabaseSettings
        assert DatabaseSettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import DatabaseSettings, BaseSettings
        assert issubclass(DatabaseSettings, BaseSettings)

    def test_default_type_is_none(self):
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        assert db.type is None

    def test_not_configured_by_default(self):
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        assert db.configured() is False

    def test_configured_after_setting_type(self):
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        db.type = "postgresql"
        assert db.configured() is True

    def test_validate_raises_when_type_is_none(self):
        """Test validate() raises ValueError when type is None."""
        import pytest
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        with pytest.raises(ValueError, match="Database must be configured"):
            db.validate()

    def test_validate_sqlite_requires_database(self):
        """Test validate() raises ValueError for SQLite without database."""
        import pytest
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        db.type = "sqlite"
        db.database = ""
        with pytest.raises(ValueError, match="SQLite requires"):
            db.validate()

    def test_validate_postgresql_requires_fields(self):
        """Test validate() raises ValueError for PostgreSQL with missing fields."""
        import pytest
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        db.type = "postgresql"
        db.host = "localhost"
        # Missing port, username, password, database
        with pytest.raises(ValueError, match="requires"):
            db.validate()

    def test_validate_unsupported_type_raises(self):
        """Test validate() raises ValueError for unsupported type."""
        import pytest
        from lys.core.configs import DatabaseSettings
        db = DatabaseSettings()
        db.type = "oracle"
        with pytest.raises(ValueError, match="Unsupported database type"):
            db.validate()


class TestCelerySettings:
    """Tests for CelerySettings class."""

    def test_class_exists(self):
        from lys.core.configs import CelerySettings
        assert CelerySettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import CelerySettings, BaseSettings
        assert issubclass(CelerySettings, BaseSettings)

    def test_configured_returns_true_by_default(self):
        """Test configured() returns True when broker_url has default value."""
        from lys.core.configs import CelerySettings
        celery = CelerySettings()
        assert celery.configured() is True

    def test_configured_returns_false_when_broker_url_is_none(self):
        """Test configured() returns False when broker_url is None."""
        from lys.core.configs import CelerySettings
        celery = CelerySettings()
        celery.broker_url = None
        assert celery.configured() is False

    def test_validate_raises_when_broker_url_empty(self):
        """Test validate() raises ValueError when broker_url is empty."""
        import pytest
        from lys.core.configs import CelerySettings
        celery = CelerySettings()
        celery.broker_url = ""
        with pytest.raises(ValueError, match="broker_url must be configured"):
            celery.validate()


class TestEmailSettings:
    """Tests for EmailSettings class."""

    def test_class_exists(self):
        from lys.core.configs import EmailSettings
        assert EmailSettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import EmailSettings, BaseSettings
        assert issubclass(EmailSettings, BaseSettings)

    def test_configured_returns_false_by_default(self):
        """Test configured() returns False when sender is None."""
        from lys.core.configs import EmailSettings
        email = EmailSettings()
        assert email.configured() is False

    def test_configured_returns_true_when_sender_set(self):
        """Test configured() returns True when sender is set."""
        from lys.core.configs import EmailSettings
        email = EmailSettings()
        email.sender = "noreply@test.com"
        assert email.configured() is True

    def test_validate_raises_when_sender_not_set(self):
        """Test validate() raises ValueError when sender is not set."""
        import pytest
        from lys.core.configs import EmailSettings
        email = EmailSettings()
        with pytest.raises(ValueError, match="sender must be configured"):
            email.validate()


class TestAISettings:
    """Tests for AISettings class."""

    def test_class_exists(self):
        from lys.core.configs import AISettings
        assert AISettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import AISettings, BaseSettings
        assert issubclass(AISettings, BaseSettings)

    def test_configured_returns_false_by_default(self):
        """Test configured() returns False when disabled."""
        from lys.core.configs import AISettings
        ai = AISettings()
        assert ai.configured() is False

    def test_configured_returns_true_when_enabled_and_api_key_set(self):
        """Test configured() returns True when enabled and api_key set."""
        from lys.core.configs import AISettings
        ai = AISettings()
        ai.enabled = True
        ai.api_key = "sk-test"
        assert ai.configured() is True

    def test_validate_raises_when_enabled_without_api_key(self):
        """Test validate() raises ValueError when enabled but api_key missing."""
        import pytest
        from lys.core.configs import AISettings
        ai = AISettings()
        ai.enabled = True
        with pytest.raises(ValueError, match="api_key is not configured"):
            ai.validate()

    def test_get_routes_manifest_returns_none_when_no_path(self):
        """Test get_routes_manifest returns None when path not set."""
        from lys.core.configs import AISettings
        ai = AISettings()
        assert ai.get_routes_manifest() is None

    def test_clear_routes_cache(self):
        """Test clear_routes_cache resets the cache."""
        from lys.core.configs import AISettings
        ai = AISettings()
        ai._routes_manifest_cache = {"some": "data"}
        ai.clear_routes_cache()
        assert ai._routes_manifest_cache is None


class TestAppSettings:
    """Tests for AppSettings class."""

    def test_class_exists(self):
        from lys.core.configs import AppSettings
        assert AppSettings is not None

    def test_has_env_attribute(self):
        from lys.core.configs import AppSettings
        app = AppSettings()
        assert hasattr(app, "env")

    def test_has_apps_attribute(self):
        from lys.core.configs import AppSettings
        app = AppSettings()
        assert hasattr(app, "apps")

    def test_has_database_attribute(self):
        from lys.core.configs import AppSettings
        app = AppSettings()
        assert hasattr(app, "database")

    def test_has_add_app_method(self):
        from lys.core.configs import AppSettings
        assert hasattr(AppSettings, "add_app")

    def test_has_configure_plugin_method(self):
        from lys.core.configs import AppSettings
        assert hasattr(AppSettings, "configure_plugin")

    def test_has_get_plugin_config_method(self):
        from lys.core.configs import AppSettings
        assert hasattr(AppSettings, "get_plugin_config")

    def test_get_plugin_config_returns_dict(self):
        from lys.core.configs import AppSettings
        app = AppSettings()
        config = app.get_plugin_config("nonexistent")
        assert isinstance(config, dict)

    def test_configure_raises_for_unknown_setting(self):
        """Test configure raises ValueError for unknown setting."""
        import pytest
        from lys.core.configs import AppSettings
        app = AppSettings()
        with pytest.raises(ValueError, match="Unknown app setting"):
            app.configure(totally_unknown_setting="value")

    def test_add_app_adds_new_app(self):
        """Test add_app adds app to the list."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.add_app("my_app")
        assert "my_app" in app.apps

    def test_add_app_does_not_duplicate(self):
        """Test add_app doesn't add duplicate app."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.add_app("my_app")
        app.add_app("my_app")
        assert app.apps.count("my_app") == 1

    def test_remove_app(self):
        """Test remove_app removes app from the list."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.add_app("my_app")
        app.remove_app("my_app")
        assert "my_app" not in app.apps

    def test_remove_app_nonexistent_is_noop(self):
        """Test remove_app with nonexistent app doesn't raise."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.remove_app("nonexistent")

    def test_add_middleware(self):
        """Test add_middleware adds middleware."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.add_middleware("my.middleware")
        assert "my.middleware" in app.middlewares

    def test_add_permission(self):
        """Test add_permission adds permission."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.add_permission("my.permission")
        assert "my.permission" in app.permissions

    def test_add_permission_does_not_duplicate(self):
        """Test add_permission doesn't add duplicate."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.add_permission("my.permission")
        app.add_permission("my.permission")
        assert app.permissions.count("my.permission") == 1

    def test_configure_plugin(self):
        """Test configure_plugin stores plugin config."""
        from lys.core.configs import AppSettings
        app = AppSettings()
        app.configure_plugin("redis", url="redis://localhost")
        config = app.get_plugin_config("redis")
        assert config["url"] == "redis://localhost"

    def test_debug_in_dev_env(self):
        """Test debug is True in DEV environment."""
        from lys.core.configs import AppSettings
        from lys.core.consts.environments import EnvironmentEnum
        app = AppSettings()
        app.env = EnvironmentEnum.DEV
        assert app.debug is True

    def test_debug_in_prod_env(self):
        """Test debug is False in PROD environment."""
        from lys.core.configs import AppSettings
        from lys.core.consts.environments import EnvironmentEnum
        app = AppSettings()
        app.env = EnvironmentEnum.PROD
        assert app.debug is False

    def test_log_level_in_dev(self):
        """Test log_level is DEBUG in DEV."""
        from lys.core.configs import AppSettings
        from lys.core.consts.environments import EnvironmentEnum
        app = AppSettings()
        app.env = EnvironmentEnum.DEV
        assert app.log_level == "DEBUG"

    def test_log_level_in_prod(self):
        """Test log_level is ERROR in PROD."""
        from lys.core.configs import AppSettings
        from lys.core.consts.environments import EnvironmentEnum
        app = AppSettings()
        app.env = EnvironmentEnum.PROD
        assert app.log_level == "ERROR"


class TestLysAppSettings:
    """Tests for LysAppSettings singleton."""

    def test_singleton_exists(self):
        from lys.core.configs import LysAppSettings
        assert LysAppSettings is not None

    def test_creates_settings_instance(self):
        from lys.core.configs import LysAppSettings
        settings = LysAppSettings()
        from lys.core.configs import AppSettings
        assert isinstance(settings, AppSettings)
