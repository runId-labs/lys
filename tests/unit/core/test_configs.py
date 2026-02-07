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


class TestCelerySettings:
    """Tests for CelerySettings class."""

    def test_class_exists(self):
        from lys.core.configs import CelerySettings
        assert CelerySettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import CelerySettings, BaseSettings
        assert issubclass(CelerySettings, BaseSettings)


class TestEmailSettings:
    """Tests for EmailSettings class."""

    def test_class_exists(self):
        from lys.core.configs import EmailSettings
        assert EmailSettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import EmailSettings, BaseSettings
        assert issubclass(EmailSettings, BaseSettings)


class TestAISettings:
    """Tests for AISettings class."""

    def test_class_exists(self):
        from lys.core.configs import AISettings
        assert AISettings is not None

    def test_inherits_from_base_settings(self):
        from lys.core.configs import AISettings, BaseSettings
        assert issubclass(AISettings, BaseSettings)


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
