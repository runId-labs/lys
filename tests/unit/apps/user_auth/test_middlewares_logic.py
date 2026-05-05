"""
Unit tests for UserAuthMiddleware dispatch logic.

Tests opaque access token resolution via AccessTokenStore (cookie vs header),
XSRF checking, and connected_user injection.

Isolation: tests build the middleware via __new__ and inject mocks for
auth_utils + a stub _build_store, so no AppManager wiring is required.
"""
import pytest
from unittest.mock import AsyncMock, Mock


def _make_request(cookies=None, headers=None, method="POST"):
    """Create a mock Starlette Request."""
    request = Mock()
    request.cookies = cookies or {}
    request.headers = headers or {}
    request.method = method
    request.state = Mock()
    return request


def _make_call_next():
    """Create a mock call_next that returns a response."""
    response = Mock()
    return AsyncMock(return_value=response), response


def _build_middleware(stored_claims=None, store_raises=None, store=None):
    """
    Construct a UserAuthMiddleware with an in-memory stub store.

    stored_claims: claims dict returned by store.get for any token id,
        or None to simulate "not found".
    store_raises: exception class to raise from store.get (simulates Redis failure).
    store: custom Mock to use as store (overrides stored_claims/store_raises).
    """
    from lys.apps.user_auth.middlewares import UserAuthMiddleware

    middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
    middleware.auth_utils = Mock()
    middleware.auth_utils.config = {}

    if store is None:
        store = Mock()
        if store_raises is not None:
            store.get = AsyncMock(side_effect=store_raises)
        else:
            store.get = AsyncMock(return_value=stored_claims)
        store.delete = AsyncMock()
        store.create = AsyncMock()

    middleware._build_store = lambda: store
    middleware._stub_store = store  # for assertions
    return middleware


class TestNoToken:
    """Tests when no token is present."""

    @pytest.mark.asyncio
    async def test_no_token_sets_none(self):
        request = _make_request()
        call_next, _ = _make_call_next()

        middleware = _build_middleware()

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        assert request.state.access_token is None
        call_next.assert_called_once_with(request)
        # Store must not even be queried when no token is present.
        middleware._stub_store.get.assert_not_called()


class TestTokenFromCookie:
    """Tests for token extraction from cookies."""

    @pytest.mark.asyncio
    async def test_valid_cookie_token_sets_user(self):
        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "abc123"}
        request = _make_request(
            cookies={"access_token": "opaque-uuid-1"},
            headers={"x-xsrf-token": "abc123"},
        )
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == claims
        assert request.state.access_token == "opaque-uuid-1"
        middleware._stub_store.get.assert_awaited_once_with("opaque-uuid-1")


class TestTokenFromHeader:
    """Tests for token extraction from Authorization header."""

    @pytest.mark.asyncio
    async def test_bearer_header_token(self):
        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "abc123"}
        request = _make_request(headers={"Authorization": "Bearer my-token"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == claims
        assert request.state.access_token == "my-token"
        middleware._stub_store.get.assert_awaited_once_with("my-token")

    @pytest.mark.asyncio
    async def test_non_bearer_header_ignored(self):
        request = _make_request(headers={"Authorization": "Basic dXNlcjpwYXNz"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims={"sub": "x", "exp": 1, "xsrf_token": "y"})

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        middleware._stub_store.get.assert_not_called()


class TestTokenNotInStore:
    """Tests for tokens that no longer resolve in the store (expired/revoked/unknown)."""

    @pytest.mark.asyncio
    async def test_unknown_token_sets_none(self):
        request = _make_request(cookies={"access_token": "unknown-uuid"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=None)

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        assert request.state.access_token is None

    @pytest.mark.asyncio
    async def test_store_failure_sets_none(self):
        """Redis/store failure must degrade to anonymous, not 500 the request."""
        request = _make_request(cookies={"access_token": "any-uuid"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(store_raises=RuntimeError("redis down"))

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        assert request.state.access_token is None


class TestNoStoreAvailable:
    """If pubsub isn't initialised, every request must be treated as anonymous."""

    @pytest.mark.asyncio
    async def test_no_store_sets_none(self):
        from lys.apps.user_auth.middlewares import UserAuthMiddleware

        request = _make_request(cookies={"access_token": "some-uuid"})
        call_next, _ = _make_call_next()

        middleware = UserAuthMiddleware.__new__(UserAuthMiddleware)
        middleware.auth_utils = Mock()
        middleware.auth_utils.config = {}
        middleware._build_store = lambda: None  # pubsub unavailable

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None
        assert request.state.access_token is None


class TestMissingClaims:
    """Tests for tokens whose stored claims are missing required fields."""

    @pytest.mark.asyncio
    async def test_missing_sub_claim_sets_none(self):
        # Missing 'sub' claim
        claims = {"exp": 9999999999, "xsrf_token": "abc123"}
        request = _make_request(cookies={"access_token": "uuid"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None

    @pytest.mark.asyncio
    async def test_missing_xsrf_claim_sets_none(self):
        # Missing 'xsrf_token' claim
        claims = {"sub": "user-1", "exp": 9999999999}
        request = _make_request(cookies={"access_token": "uuid"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)

        await middleware.dispatch(request, call_next)

        assert request.state.connected_user is None


class TestXSRFValidation:
    """Tests for XSRF token validation."""

    @pytest.mark.asyncio
    async def test_xsrf_mismatch_raises(self):
        from lys.core.errors import LysError

        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "expected-token"}
        request = _make_request(
            cookies={"access_token": "uuid"},
            headers={"x-xsrf-token": "wrong-token"},
        )
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        with pytest.raises(LysError, match="INVALID_XSRF_TOKEN_ERROR"):
            await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_xsrf_missing_header_raises(self):
        from lys.core.errors import LysError

        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "expected-token"}
        request = _make_request(cookies={"access_token": "uuid"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        with pytest.raises(LysError, match="INVALID_XSRF_TOKEN_ERROR"):
            await middleware.dispatch(request, call_next)

    @pytest.mark.asyncio
    async def test_xsrf_skipped_for_bearer(self):
        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "token"}
        request = _make_request(headers={"Authorization": "Bearer my-token"})
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        # Should NOT raise even though no x-xsrf-token header
        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == claims

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    async def test_xsrf_skipped_for_safe_methods(self, method):
        """XSRF check is skipped for safe HTTP methods (GET, HEAD, OPTIONS)."""
        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "token"}
        request = _make_request(
            cookies={"access_token": "uuid"},
            method=method,
        )
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        # Should NOT raise even though no x-xsrf-token header
        await middleware.dispatch(request, call_next)

        assert request.state.connected_user == claims

    @pytest.mark.asyncio
    async def test_xsrf_enforced_for_post(self):
        """XSRF check is enforced for POST requests with cookie auth."""
        from lys.core.errors import LysError

        claims = {"sub": "user-1", "exp": 9999999999, "xsrf_token": "expected-token"}
        request = _make_request(
            cookies={"access_token": "uuid"},
            method="POST",
        )
        call_next, _ = _make_call_next()

        middleware = _build_middleware(stored_claims=claims)
        middleware.auth_utils.config = {"check_xsrf_token": True}

        with pytest.raises(LysError, match="INVALID_XSRF_TOKEN_ERROR"):
            await middleware.dispatch(request, call_next)
