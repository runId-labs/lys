"""
Unit tests for CLI functions (run_fast_app, export_graphql_schema).
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lys.core.clis import run_fast_app, export_graphql_schema


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
