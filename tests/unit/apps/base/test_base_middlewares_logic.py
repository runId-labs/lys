"""
Unit tests for base app ServiceAuthMiddleware.

Tests cover:
- Valid service token in Authorization header
- Invalid token
- Missing Authorization header
- Wrong Authorization prefix
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from jwt import InvalidTokenError, ExpiredSignatureError


class TestServiceAuthMiddleware:
    """Test ServiceAuthMiddleware dispatch logic."""

    def _make_request(self, auth_header=None):
        """Create a mock Starlette Request."""
        request = MagicMock()
        headers = {}
        if auth_header is not None:
            headers["Authorization"] = auth_header
        request.headers = headers
        request.state = MagicMock()
        return request

    @pytest.mark.asyncio
    async def test_valid_service_token(self):
        """Test valid service JWT sets service_caller on request.state."""
        with patch("lys.apps.base.middlewares.AppManagerCallerMixin") as mock_mixin:
            from lys.apps.base.middlewares import ServiceAuthMiddleware

            decoded = {"type": "service", "service_name": "test-service"}
            mock_auth_utils = MagicMock()
            mock_auth_utils.decode_token.return_value = decoded

            middleware = object.__new__(ServiceAuthMiddleware)
            middleware.auth_utils = mock_auth_utils

            request = self._make_request("Service valid-jwt-token")
            call_next = AsyncMock(return_value=MagicMock())

            await middleware.dispatch(request, call_next)

            mock_auth_utils.decode_token.assert_called_once_with("valid-jwt-token")
            assert request.state.service_caller == decoded
            call_next.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test invalid JWT sets service_caller to None."""
        with patch("lys.apps.base.middlewares.AppManagerCallerMixin"):
            from lys.apps.base.middlewares import ServiceAuthMiddleware

            mock_auth_utils = MagicMock()
            mock_auth_utils.decode_token.side_effect = InvalidTokenError("bad token")

            middleware = object.__new__(ServiceAuthMiddleware)
            middleware.auth_utils = mock_auth_utils

            request = self._make_request("Service bad-token")
            call_next = AsyncMock(return_value=MagicMock())

            await middleware.dispatch(request, call_next)

            assert request.state.service_caller is None
            call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_expired_token(self):
        """Test expired JWT sets service_caller to None."""
        with patch("lys.apps.base.middlewares.AppManagerCallerMixin"):
            from lys.apps.base.middlewares import ServiceAuthMiddleware

            mock_auth_utils = MagicMock()
            mock_auth_utils.decode_token.side_effect = ExpiredSignatureError("expired")

            middleware = object.__new__(ServiceAuthMiddleware)
            middleware.auth_utils = mock_auth_utils

            request = self._make_request("Service expired-token")
            call_next = AsyncMock(return_value=MagicMock())

            await middleware.dispatch(request, call_next)

            assert request.state.service_caller is None
            call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_authorization_header(self):
        """Test missing Authorization header sets service_caller to None."""
        with patch("lys.apps.base.middlewares.AppManagerCallerMixin"):
            from lys.apps.base.middlewares import ServiceAuthMiddleware

            mock_auth_utils = MagicMock()

            middleware = object.__new__(ServiceAuthMiddleware)
            middleware.auth_utils = mock_auth_utils

            request = self._make_request()
            call_next = AsyncMock(return_value=MagicMock())

            await middleware.dispatch(request, call_next)

            mock_auth_utils.decode_token.assert_not_called()
            assert request.state.service_caller is None

    @pytest.mark.asyncio
    async def test_wrong_prefix(self):
        """Test non-Service prefix does not attempt to decode."""
        with patch("lys.apps.base.middlewares.AppManagerCallerMixin"):
            from lys.apps.base.middlewares import ServiceAuthMiddleware

            mock_auth_utils = MagicMock()

            middleware = object.__new__(ServiceAuthMiddleware)
            middleware.auth_utils = mock_auth_utils

            request = self._make_request("Bearer some-jwt")
            call_next = AsyncMock(return_value=MagicMock())

            await middleware.dispatch(request, call_next)

            mock_auth_utils.decode_token.assert_not_called()
            assert request.state.service_caller is None
