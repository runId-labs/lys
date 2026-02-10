"""
Unit tests for core middlewares module logic.

Tests _MiddlewareLysError and ErrorManagerMiddleware.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from lys.core.consts.environments import EnvironmentEnum
from lys.core.middlewares import (
    _MiddlewareLysError, ErrorManagerMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware
)


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


class TestSecurityHeadersMiddleware:

    def _make_request(self, scheme="http"):
        request = MagicMock()
        request.url.scheme = scheme
        return request

    def _make_response(self):
        response = MagicMock()
        response.headers = {}
        return response

    def test_sets_content_type_options(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert result.headers["X-Content-Type-Options"] == "nosniff"

    def test_sets_frame_options(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert result.headers["X-Frame-Options"] == "DENY"

    def test_sets_referrer_policy(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert result.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_sets_permissions_policy(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert result.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_no_hsts_on_http(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request(scheme="http")
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert "Strict-Transport-Security" not in result.headers

    def test_hsts_on_https(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request(scheme="https")
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert result.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_all_headers_present_on_https(self):
        middleware = SecurityHeadersMiddleware(MagicMock())
        request = self._make_request(scheme="https")
        response = self._make_response()

        async def call_next(_):
            return response

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(middleware.dispatch(request, call_next))
        finally:
            loop.close()

        assert "X-Content-Type-Options" in result.headers
        assert "X-Frame-Options" in result.headers
        assert "Referrer-Policy" in result.headers
        assert "Permissions-Policy" in result.headers
        assert "Strict-Transport-Security" in result.headers


class TestRateLimitMiddleware:

    def _make_request(self, ip="127.0.0.1", headers=None):
        request = MagicMock()
        request.client.host = ip
        request.headers = headers or {}
        return request

    def _make_response(self):
        return MagicMock()

    def _create_middleware(self, config=None, pubsub=None):
        mock_app_manager = MagicMock()
        mock_app_manager.settings.plugins = {}
        if config:
            mock_app_manager.settings.plugins["rate_limit"] = config
        mock_app_manager.pubsub = pubsub

        with patch.object(RateLimitMiddleware, "app_manager", mock_app_manager):
            middleware = RateLimitMiddleware(MagicMock())
        return middleware, mock_app_manager

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_default_config(self):
        middleware, _ = self._create_middleware()
        assert middleware.requests_per_minute == 60
        assert middleware.enabled is True

    def test_custom_config(self):
        middleware, _ = self._create_middleware({"requests_per_minute": 100, "enabled": False})
        assert middleware.requests_per_minute == 100
        assert middleware.enabled is False

    def test_disabled_passes_through(self):
        middleware, _ = self._create_middleware({"enabled": False})
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        result = self._run(middleware.dispatch(request, call_next))
        assert result is response

    def test_allows_under_limit_memory(self):
        middleware, mock_am = self._create_middleware({"requests_per_minute": 5})
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            result = self._run(middleware.dispatch(request, call_next))

        assert result is response

    def test_blocks_over_limit_memory(self):
        middleware, mock_am = self._create_middleware({"requests_per_minute": 3})
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            # Send 3 allowed requests
            for _ in range(3):
                self._run(middleware.dispatch(request, call_next))

            # 4th request should be blocked
            result = self._run(middleware.dispatch(request, call_next))

        assert result.status_code == 429
        assert result.body is not None

    def test_different_ips_have_separate_limits(self):
        middleware, mock_am = self._create_middleware({"requests_per_minute": 2})
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            # Exhaust limit for IP A
            for _ in range(2):
                self._run(middleware.dispatch(self._make_request("10.0.0.1"), call_next))

            # IP A blocked
            result_a = self._run(middleware.dispatch(self._make_request("10.0.0.1"), call_next))
            assert result_a.status_code == 429

            # IP B still allowed
            result_b = self._run(middleware.dispatch(self._make_request("10.0.0.2"), call_next))
            assert result_b is response

    def test_429_has_retry_after_header(self):
        middleware, mock_am = self._create_middleware({"requests_per_minute": 1})
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            self._run(middleware.dispatch(request, call_next))
            result = self._run(middleware.dispatch(request, call_next))

        assert result.status_code == 429
        assert result.headers["Retry-After"] == "60"

    def test_uses_redis_when_available(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()

        mock_pubsub = MagicMock()
        mock_pubsub._async_redis = mock_redis

        middleware, mock_am = self._create_middleware(pubsub=mock_pubsub)
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            result = self._run(middleware.dispatch(request, call_next))

        assert result is response
        mock_redis.incr.assert_called_once_with("rate_limit:127.0.0.1")
        mock_redis.expire.assert_called_once_with("rate_limit:127.0.0.1", 60)

    def test_redis_over_limit_returns_429(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=61)

        mock_pubsub = MagicMock()
        mock_pubsub._async_redis = mock_redis

        middleware, mock_am = self._create_middleware(pubsub=mock_pubsub)
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            result = self._run(middleware.dispatch(request, call_next))

        assert result.status_code == 429

    def test_redis_expire_only_on_first_incr(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)

        mock_pubsub = MagicMock()
        mock_pubsub._async_redis = mock_redis

        middleware, mock_am = self._create_middleware(pubsub=mock_pubsub)
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            self._run(middleware.dispatch(request, call_next))

        mock_redis.expire.assert_not_called()

    def test_redis_failure_allows_request(self):
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(side_effect=Exception("Redis down"))

        mock_pubsub = MagicMock()
        mock_pubsub._async_redis = mock_redis

        middleware, mock_am = self._create_middleware(pubsub=mock_pubsub)
        request = self._make_request()
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            result = self._run(middleware.dispatch(request, call_next))

        assert result is response

    def test_no_client_uses_unknown_ip(self):
        middleware, mock_am = self._create_middleware({"requests_per_minute": 1})
        request = MagicMock()
        request.client = None
        request.headers = {}
        response = self._make_response()

        async def call_next(_):
            return response

        with patch.object(RateLimitMiddleware, "app_manager", mock_am):
            self._run(middleware.dispatch(request, call_next))

        assert "rate_limit:unknown" in middleware._memory_store
