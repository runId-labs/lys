"""
Unit tests for core middlewares module logic.

Tests _MiddlewareLysError and ErrorManagerMiddleware.
"""

import asyncio
from unittest.mock import MagicMock, patch

from lys.core.consts.environments import EnvironmentEnum
from lys.core.middlewares import _MiddlewareLysError, ErrorManagerMiddleware


class TestMiddlewareLysError:

    def test_dev_includes_debug_info(self):
        mock_app_manager = MagicMock()
        mock_app_manager.settings.env = EnvironmentEnum.DEV

        with patch.object(_MiddlewareLysError, "app_manager", mock_app_manager):
            err = _MiddlewareLysError(400, "BAD", "debug msg", "file.py", 42, "traceback str")

        assert err.extensions["debug_message"] == "debug msg"
        assert err.extensions["file_name"] == "file.py"
        assert err.extensions["line"] == 42
        assert err.extensions["traceback"] == "traceback str"

    def test_prod_no_debug_info(self):
        mock_app_manager = MagicMock()
        mock_app_manager.settings.env = EnvironmentEnum.PROD

        with patch.object(_MiddlewareLysError, "app_manager", mock_app_manager):
            err = _MiddlewareLysError(500, "ERROR", "debug msg", "file.py", 42, "traceback str")

        assert "debug_message" not in err.extensions
        assert "file_name" not in err.extensions
        assert "line" not in err.extensions
        assert "traceback" not in err.extensions

    def test_public_extensions_passed_through(self):
        mock_app_manager = MagicMock()
        mock_app_manager.settings.env = EnvironmentEnum.PROD

        with patch.object(_MiddlewareLysError, "app_manager", mock_app_manager):
            err = _MiddlewareLysError(
                400, "BAD", "debug", "f.py", 1, "tb",
                public_extensions={"code": "CUSTOM"}
            )

        assert err.extensions["code"] == "CUSTOM"

    def test_dev_with_public_extensions_merges(self):
        mock_app_manager = MagicMock()
        mock_app_manager.settings.env = EnvironmentEnum.DEV

        with patch.object(_MiddlewareLysError, "app_manager", mock_app_manager):
            err = _MiddlewareLysError(
                400, "BAD", "debug msg", "file.py", 42, "tb",
                public_extensions={"code": "CUSTOM"}
            )

        assert err.extensions["code"] == "CUSTOM"
        assert err.extensions["debug_message"] == "debug msg"

    def test_http_exception_status_code(self):
        mock_app_manager = MagicMock()
        mock_app_manager.settings.env = EnvironmentEnum.PROD

        with patch.object(_MiddlewareLysError, "app_manager", mock_app_manager):
            err = _MiddlewareLysError(404, "NOT_FOUND", "debug", "f.py", 1, "tb")

        assert err.status_code == 404
        assert err.detail == "NOT_FOUND"


class TestErrorManagerMiddleware:

    def test_init_default_context_keys(self):
        mock_app = MagicMock()
        middleware = ErrorManagerMiddleware(mock_app)
        assert "connected_user" in middleware.saved_context_keys
        assert "webservice_name" in middleware.saved_context_keys
        assert "access_type" in middleware.saved_context_keys
        assert "webservice_parameters" in middleware.saved_context_keys

    def test_init_custom_context_keys(self):
        mock_app = MagicMock()
        middleware = ErrorManagerMiddleware(mock_app, saved_context_keys=["custom_key"])
        assert middleware.saved_context_keys == ["custom_key"]

    def test_get_from_request_state(self):
        mock_request = MagicMock()
        mock_request.state.test_key = "test_value"
        result = ErrorManagerMiddleware._get_from_request_state(mock_request, "test_key")
        assert result == "test_value"

    def test_get_from_request_state_missing(self):
        mock_request = MagicMock()
        mock_state = MagicMock(spec=[])
        mock_request.state = mock_state
        result = ErrorManagerMiddleware._get_from_request_state(mock_request, "nonexistent")
        assert result is None

    def test_get_context_from_request_with_values(self):
        mock_app = MagicMock()
        middleware = ErrorManagerMiddleware(mock_app)
        mock_request = MagicMock()
        mock_request.state.connected_user = {"sub": "user1"}
        mock_request.state.webservice_name = "test_ws"
        mock_request.state.access_type = None
        mock_request.state.webservice_parameters = None

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                middleware._get_context_from_request(mock_request)
            )
        finally:
            loop.close()

        assert result["connected_user"] == {"sub": "user1"}
        assert result["webservice_name"] == "test_ws"

    def test_get_context_from_request_all_none_returns_none(self):
        mock_app = MagicMock()
        middleware = ErrorManagerMiddleware(mock_app)
        mock_request = MagicMock()
        mock_state = MagicMock(spec=[])
        mock_request.state = mock_state

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                middleware._get_context_from_request(mock_request)
            )
        finally:
            loop.close()

        assert result is None

    def test_get_context_from_request_partial_values(self):
        mock_app = MagicMock()
        middleware = ErrorManagerMiddleware(mock_app, saved_context_keys=["key1", "key2"])
        mock_request = MagicMock()
        mock_request.state.key1 = "value1"
        mock_request.state.key2 = None

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                middleware._get_context_from_request(mock_request)
            )
        finally:
            loop.close()

        assert result == {"key1": "value1"}
        assert "key2" not in result
