"""
Unit tests for UserAuthMiddleware dispatch logic.

Tests token extraction (cookie vs header), JWT validation, XSRF checking,
and connected_user injection.

Isolation: All tests use inline imports + patch. No global state modified.
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock


def _make_request(cookies=None, headers=None):
    """Create a mock Starlette Request."""
    request = Mock()
    request.cookies = cookies or {}
    request.headers = headers or {}
    request.state = Mock()
    return request


def _make_call_next():
    """Create a mock call_next that returns a response."""
    response = Mock()
    return AsyncMock(return_value=response), response


class TestNoToken:
    """Tests when no token is present."""

    @pytest.mark.asyncio
    async def test_no_token_sets_none(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        request = _make_request()
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        assert request.state.access_token is None
        call_next.assert_called_once_with(request)


class TestTokenFromCookie:
    """Tests for token extraction from cookies."""

    @pytest.mark.asyncio
    async def test_valid_cookie_token_sets_user(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        jwt_claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "abc123"}
        request = _make_request(
            cookies={"access_token": "valid-jwt"},
            headers={"x-xsrf-token": "abc123"},
        )
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {}

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == jwt_claims
        assert request.state.access_token == "valid-jwt"


class TestTokenFromHeader:
    """Tests for token extraction from Authorization header."""

    @pytest.mark.asyncio
    async def test_bearer_header_token(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        jwt_claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "abc123"}
        request = _make_request(headers={"Authorization": "Bearer my-token"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {}

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == jwt_claims
        assert request.state.access_token == "my-token"

    @pytest.mark.asyncio
    async def test_non_bearer_header_ignored(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        request = _make_request(headers={"Authorization": "Basic dXNlcjpwYXNz"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None


class TestExpiredToken:
    """Tests for expired/invalid tokens."""

    @pytest.mark.asyncio
    async def test_expired_token_sets_none(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware
        from jwt import ExpiredSignatureError

        request = _make_request(cookies={"access_token": "expired-jwt"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(side_effect=ExpiredSignatureError("expired"))

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        assert request.state.access_token is None

    @pytest.mark.asyncio
    async def test_invalid_token_sets_none(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware
        from jwt import InvalidTokenError

        request = _make_request(cookies={"access_token": "bad-jwt"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(side_effect=InvalidTokenError("invalid"))

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None


class TestMissingClaims:
    """Tests for tokens with missing required claims."""

    @pytest.mark.asyncio
    async def test_missing_sub_claim_sets_none(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        # Missing 'sub' claim
        jwt_claims = {"exp": 9999999999, "xsrf_token": "abc123"}
        request = _make_request(cookies={"access_token": "valid-jwt"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {}

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None

    @pytest.mark.asyncio
    async def test_missing_xsrf_claim_sets_none(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        # Missing 'xsrf_token' claim
        jwt_claims = {"sub": "user-1", "exp": 9999999999}
        request = _make_request(cookies={"access_token": "valid-jwt"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {}

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None


class TestXSRFValidation:
    """Tests for XSRF token validation."""

    @pytest.mark.asyncio
    async def test_xsrf_mismatch_raises(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware
        from lys.core.errors import LysError

        jwt_claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "expected-token"}
        request = _make_request(
            cookies={"access_token": "valid-jwt"},
            headers={"x-xsrf-token": "wrong-token"}
        )
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        with pytest.raises(LysError, match="INVALID_XSRF_TOKEN_ERROR"):
            await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_xsrf_missing_header_raises(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware
        from lys.core.errors import LysError

        jwt_claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "expected-token"}
        request = _make_request(cookies={"access_token": "valid-jwt"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        with pytest.raises(LysError, match="INVALID_XSRF_TOKEN_ERROR"):
            await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_xsrf_skipped_for_bearer(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        jwt_claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "token"}
        request = _make_request(headers={"Authorization": "Bearer my-jwt"})
        call_next, response = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.decode = AsyncMock(return_value=jwt_claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        # Should NOT raise even though no x-xsrf-token header
        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == jwt_claims
