"""
Unit tests for CLI functions (run_fast_app, export_graphql_schema, Alembic wrappers).
"""
import os

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lys.core.clis import (
    run_fast_app, export_graphql_schema,
    _find_alembic_ini, run_migrate, run_makemigrations, run_db_status, run_db_stamp,
)


class TestRunFastApp:
    def test_missing_app_file_raises(self, tmp_path):
        missing_path = tmp_path / "nonexistent.py"
        with pytest.raises(Exception, match="App file not found"):
            run_fast_app(
                host="0.0.0.0", port=8000, reload=False, workers=1,
                app_path=missing_path, ssl_certfile=None, ssl_keyfile=None,
            )

    @patch("lys.core.clis.get_import_data")
    @patch("lys.core.clis.uvicorn")
    def test_successful_run(self, mock_uvicorn, mock_get_import_data, tmp_path):
        app_file = tmp_path / "main.py"
        app_file.write_text("app = None")
        mock_import_data = MagicMock()
        mock_import_data.import_string = "main:app"
        mock_get_import_data.return_value = mock_import_data

        run_fast_app(
            host="0.0.0.0", port=8000, reload=False, workers=1,
            app_path=app_file, ssl_certfile=None, ssl_keyfile=None,
        )
        mock_uvicorn.run.assert_called_once()

    @patch("lys.core.clis.get_import_data")
    def test_fastapi_discovery_failure(self, mock_get_import_data, tmp_path):
        from fastapi_cli.exceptions import FastAPICLIException
        app_file = tmp_path / "main.py"
        app_file.write_text("app = None")
        mock_get_import_data.side_effect = FastAPICLIException("discovery failed")
        with pytest.raises(Exception, match="Failed to discover FastAPI app"):
            run_fast_app(
                host="0.0.0.0", port=8000, reload=False, workers=1,
                app_path=app_file, ssl_certfile=None, ssl_keyfile=None,
            )

    @patch("lys.core.clis.get_import_data")
    @patch("lys.core.clis.uvicorn")
    def test_with_ssl_and_timeout(self, mock_uvicorn, mock_get_import_data, tmp_path):
        app_file = tmp_path / "main.py"
        app_file.write_text("app = None")
        mock_import_data = MagicMock()
        mock_import_data.import_string = "main:app"
        mock_get_import_data.return_value = mock_import_data

        run_fast_app(
            host="0.0.0.0", port=443, reload=True, workers=4,
            app_path=app_file, ssl_certfile="/cert.pem", ssl_keyfile="/key.pem",
            timeout_graceful_shutdown=30,
        )
        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs["ssl_certfile"] == "/cert.pem"
        assert call_kwargs["ssl_keyfile"] == "/key.pem"
        assert call_kwargs["timeout_graceful_shutdown"] == 30


class TestExportGraphqlSchema:
    @patch("importlib.import_module")
    def test_missing_configure_core_raises(self, mock_import_module, tmp_path):
        mock_settings = MagicMock(spec=[])
        mock_import_module.return_value = mock_settings
        with pytest.raises(Exception, match="configure_core"):
            export_graphql_schema(output_path=tmp_path / "schema.graphql")

    @patch("importlib.import_module")
    def test_import_error_raises(self, mock_import_module, tmp_path):
        mock_import_module.side_effect = ImportError("module not found")
        with pytest.raises(Exception, match="Failed to import settings module"):
            export_graphql_schema(output_path=tmp_path / "schema.graphql")


class TestFindAlembicIni:
    """Tests for _find_alembic_ini()."""

    def test_finds_alembic_ini_in_cwd(self, tmp_path):
        ini_file = tmp_path / "alembic.ini"
        ini_file.write_text("[alembic]\n")
        with patch("lys.core.clis.os.getcwd", return_value=str(tmp_path)):
            result = _find_alembic_ini()
        assert result == str(ini_file)

    def test_raises_when_not_found(self, tmp_path):
        with patch("lys.core.clis.os.getcwd", return_value=str(tmp_path)):
            with pytest.raises(FileNotFoundError, match="alembic.ini not found"):
                _find_alembic_ini()


class TestRunMigrate:
    """Tests for run_migrate()."""

    @patch("lys.core.clis._find_alembic_ini", return_value="/fake/alembic.ini")
    @patch("alembic.command.upgrade")
    @patch("alembic.config.Config")
    def test_calls_upgrade_with_head(self, mock_config_cls, mock_upgrade, mock_find):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        run_migrate()
        mock_config_cls.assert_called_once_with("/fake/alembic.ini")
        mock_upgrade.assert_called_once_with(mock_cfg, "head")

    @patch("lys.core.clis._find_alembic_ini", return_value="/fake/alembic.ini")
    @patch("alembic.command.upgrade")
    @patch("alembic.config.Config")
    def test_calls_upgrade_with_custom_revision(self, mock_config_cls, mock_upgrade, mock_find):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        run_migrate(revision="abc123")
        mock_upgrade.assert_called_once_with(mock_cfg, "abc123")


class TestRunMakemigrations:
    """Tests for run_makemigrations()."""

    @patch("lys.core.clis._find_alembic_ini", return_value="/fake/alembic.ini")
    @patch("alembic.command.revision")
    @patch("alembic.config.Config")
    def test_calls_revision_autogenerate(self, mock_config_cls, mock_revision, mock_find):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        run_makemigrations("add users table")
        mock_revision.assert_called_once_with(
            mock_cfg, message="add users table", autogenerate=True
        )


class TestRunDbStatus:
    """Tests for run_db_status()."""

    @patch("lys.core.clis._find_alembic_ini", return_value="/fake/alembic.ini")
    @patch("alembic.command.current")
    @patch("alembic.config.Config")
    def test_calls_current(self, mock_config_cls, mock_current, mock_find):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        run_db_status()
        mock_current.assert_called_once_with(mock_cfg, verbose=True)


class TestRunDbStamp:
    """Tests for run_db_stamp()."""

    @patch("lys.core.clis._find_alembic_ini", return_value="/fake/alembic.ini")
    @patch("alembic.command.stamp")
    @patch("alembic.config.Config")
    def test_calls_stamp_with_head(self, mock_config_cls, mock_stamp, mock_find):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        run_db_stamp()
        mock_stamp.assert_called_once_with(mock_cfg, "head")

    @patch("lys.core.clis._find_alembic_ini", return_value="/fake/alembic.ini")
    @patch("alembic.command.stamp")
    @patch("alembic.config.Config")
    def test_calls_stamp_with_custom_revision(self, mock_config_cls, mock_stamp, mock_find):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        run_db_stamp(revision="abc123")
        mock_stamp.assert_called_once_with(mock_cfg, "abc123")
