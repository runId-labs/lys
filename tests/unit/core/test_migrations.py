"""
Unit tests for Alembic migration helper (configure_alembic_env).
"""
from unittest.mock import patch, MagicMock

import pytest

import lys.core.migrations as migrations_module
import lys.core.managers.database as database_module


class TestConfigureAlembicEnv:
    """Tests for configure_alembic_env()."""

    def test_raises_on_missing_settings_module(self):
        mock_import = MagicMock(side_effect=ImportError("no module"))
        with patch.object(migrations_module, "importlib", MagicMock(import_module=mock_import)), \
             patch.object(migrations_module, "context", MagicMock()), \
             patch.object(migrations_module, "LysAppManager", MagicMock()):
            with pytest.raises(RuntimeError, match="Failed to import settings module"):
                migrations_module.configure_alembic_env("nonexistent")

    def test_raises_on_missing_configure_core(self):
        mock_settings = MagicMock(spec=[])
        with patch.object(migrations_module, "importlib", MagicMock(import_module=MagicMock(return_value=mock_settings))), \
             patch.object(migrations_module, "context", MagicMock()), \
             patch.object(migrations_module, "LysAppManager", MagicMock()):
            with pytest.raises(RuntimeError, match="configure_core"):
                migrations_module.configure_alembic_env()

    def test_raises_on_missing_configure_database(self):
        mock_settings = MagicMock(spec=["configure_core"])
        with patch.object(migrations_module, "importlib", MagicMock(import_module=MagicMock(return_value=mock_settings))), \
             patch.object(migrations_module, "context", MagicMock()), \
             patch.object(migrations_module, "LysAppManager", MagicMock()):
            with pytest.raises(RuntimeError, match="configure_database"):
                migrations_module.configure_alembic_env()

    def test_calls_offline_mode(self):
        mock_settings = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.is_offline_mode.return_value = True
        mock_db = MagicMock()
        mock_db._build_url.return_value = "sqlite:///test.db"

        with patch.object(migrations_module, "importlib", MagicMock(import_module=MagicMock(return_value=mock_settings))), \
             patch.object(migrations_module, "context", mock_ctx), \
             patch.object(migrations_module, "LysAppManager", MagicMock()), \
             patch.object(database_module, "DatabaseManager", MagicMock(return_value=mock_db)), \
             patch.object(migrations_module, "_run_migrations_offline") as mock_offline:
            migrations_module.configure_alembic_env()

        mock_offline.assert_called_once()
        mock_settings.configure_core.assert_called_once()
        mock_settings.configure_database.assert_called_once()

    def test_calls_online_mode(self):
        mock_settings = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.is_offline_mode.return_value = False
        mock_db = MagicMock()
        mock_db._build_url.return_value = "sqlite:///test.db"

        with patch.object(migrations_module, "importlib", MagicMock(import_module=MagicMock(return_value=mock_settings))), \
             patch.object(migrations_module, "context", mock_ctx), \
             patch.object(migrations_module, "LysAppManager", MagicMock()), \
             patch.object(database_module, "DatabaseManager", MagicMock(return_value=mock_db)), \
             patch.object(migrations_module, "_run_migrations_online") as mock_online:
            migrations_module.configure_alembic_env()

        mock_online.assert_called_once()

    def test_loads_entities_component(self):
        from lys.core.consts.component_types import AppComponentTypeEnum

        mock_settings = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.is_offline_mode.return_value = False
        mock_db = MagicMock()
        mock_db._build_url.return_value = "sqlite:///test.db"
        mock_mgr = MagicMock()

        with patch.object(migrations_module, "importlib", MagicMock(import_module=MagicMock(return_value=mock_settings))), \
             patch.object(migrations_module, "context", mock_ctx), \
             patch.object(migrations_module, "LysAppManager", MagicMock(return_value=mock_mgr)), \
             patch.object(database_module, "DatabaseManager", MagicMock(return_value=mock_db)), \
             patch.object(migrations_module, "_run_migrations_online"):
            migrations_module.configure_alembic_env()

        mock_mgr.configure_component_types.assert_called_once_with([AppComponentTypeEnum.ENTITIES])
        mock_mgr.load_all_components.assert_called_once()


class TestRunMigrationsOffline:
    """Tests for _run_migrations_offline()."""

    def test_configures_context_and_runs(self):
        mock_ctx = MagicMock()
        mock_metadata = MagicMock()

        with patch.object(migrations_module, "context", mock_ctx):
            migrations_module._run_migrations_offline("sqlite:///test.db", mock_metadata)

        mock_ctx.configure.assert_called_once_with(
            url="sqlite:///test.db",
            target_metadata=mock_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        mock_ctx.begin_transaction.assert_called_once()
        mock_ctx.run_migrations.assert_called_once()


class TestRunMigrationsOnline:
    """Tests for _run_migrations_online()."""

    @patch("sqlalchemy.engine_from_config")
    def test_creates_engine_and_runs(self, mock_engine_from_config):
        mock_ctx = MagicMock()
        mock_ctx.config.config_ini_section = "alembic"
        mock_ctx.config.get_section.return_value = {}
        mock_metadata = MagicMock()
        mock_connectable = MagicMock()
        mock_connection = MagicMock()
        mock_connectable.connect.return_value.__enter__ = MagicMock(return_value=mock_connection)
        mock_connectable.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_engine_from_config.return_value = mock_connectable

        with patch.object(migrations_module, "context", mock_ctx):
            migrations_module._run_migrations_online("sqlite:///test.db", mock_metadata)

        mock_ctx.config.set_main_option.assert_called_once_with("sqlalchemy.url", "sqlite:///test.db")
        mock_ctx.configure.assert_called_once()
        mock_ctx.run_migrations.assert_called_once()
