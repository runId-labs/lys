"""
Unit tests for base app middlewares.

Tests ServiceAuthMiddleware with mocked dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


class TestServiceAuthMiddlewareInit:
    """Tests for ServiceAuthMiddleware initialization."""

    def test_authorization_prefix_constant(self):
        """Test AUTHORIZATION_PREFIX is correctly defined."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware

        assert ServiceAuthMiddleware.AUTHORIZATION_PREFIX == "Service "


class TestServiceAuthMiddlewareDispatch:
    """Tests for ServiceAuthMiddleware.dispatch method."""

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app manager."""
        app_manager = MagicMock()
        app_manager.settings.secret_key = "test_secret_key"
        return app_manager

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.headers = {}
        request.state = MagicMock()
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create mock call_next function."""
        async def call_next(request):
            return MagicMock(status_code=200)
        return call_next

    @pytest.mark.asyncio
    async def test_dispatch_without_auth_header(self, mock_request, mock_call_next, mock_app_manager):
        """Test dispatch when no Authorization header is present."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware

        mock_request.headers = {}

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
            middleware = ServiceAuthMiddleware(MagicMock())
            await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.service_caller is None

    @pytest.mark.asyncio
    async def test_dispatch_with_non_service_auth_header(self, mock_request, mock_call_next, mock_app_manager):
        """Test dispatch when Authorization header doesn't start with 'Service '."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware

        mock_request.headers = {"Authorization": "Bearer some_token"}

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
            middleware = ServiceAuthMiddleware(MagicMock())
            await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.service_caller is None

    @pytest.mark.asyncio
    async def test_dispatch_with_valid_service_token(self, mock_request, mock_call_next, mock_app_manager):
        """Test dispatch with valid service JWT token."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware

        mock_request.headers = {"Authorization": "Service valid_token_here"}

        mock_auth_utils = MagicMock()
        mock_auth_utils.decode_token.return_value = {"service_name": "test-service"}

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
             with patch('lys.apps.base.middlewares.ServiceAuthUtils', return_value=mock_auth_utils):
                middleware = ServiceAuthMiddleware(MagicMock())
                middleware.auth_utils = mock_auth_utils
                await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.service_caller == {"service_name": "test-service"}

    @pytest.mark.asyncio
    async def test_dispatch_with_expired_token(self, mock_request, mock_call_next, mock_app_manager):
        """Test dispatch with expired service JWT token."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware
        from jwt import ExpiredSignatureError

        mock_request.headers = {"Authorization": "Service expired_token"}

        mock_auth_utils = MagicMock()
        mock_auth_utils.decode_token.side_effect = ExpiredSignatureError("Token expired")

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
            with patch('lys.apps.base.middlewares.ServiceAuthUtils', return_value=mock_auth_utils):
                middleware = ServiceAuthMiddleware(MagicMock())
                middleware.auth_utils = mock_auth_utils
                await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.service_caller is None

    @pytest.mark.asyncio
    async def test_dispatch_with_invalid_token(self, mock_request, mock_call_next, mock_app_manager):
        """Test dispatch with invalid service JWT token."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware
        from jwt import InvalidTokenError

        mock_request.headers = {"Authorization": "Service invalid_token"}

        mock_auth_utils = MagicMock()
        mock_auth_utils.decode_token.side_effect = InvalidTokenError("Invalid token")

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
            with patch('lys.apps.base.middlewares.ServiceAuthUtils', return_value=mock_auth_utils):
                middleware = ServiceAuthMiddleware(MagicMock())
                middleware.auth_utils = mock_auth_utils
                await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.service_caller is None

    @pytest.mark.asyncio
    async def test_dispatch_with_unexpected_error(self, mock_request, mock_call_next, mock_app_manager):
        """Test dispatch with unexpected error during token validation."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware

        mock_request.headers = {"Authorization": "Service some_token"}

        mock_auth_utils = MagicMock()
        mock_auth_utils.decode_token.side_effect = Exception("Unexpected error")

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
            with patch('lys.apps.base.middlewares.ServiceAuthUtils', return_value=mock_auth_utils):
                middleware = ServiceAuthMiddleware(MagicMock())
                middleware.auth_utils = mock_auth_utils
                await middleware.dispatch(mock_request, mock_call_next)

        assert mock_request.state.service_caller is None

    @pytest.mark.asyncio
    async def test_dispatch_calls_next_middleware(self, mock_request, mock_app_manager):
        """Test that dispatch calls call_next."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware

        mock_request.headers = {}
        call_next_called = False
        expected_response = MagicMock(status_code=200)

        async def mock_call_next(request):
            nonlocal call_next_called
            call_next_called = True
            return expected_response

        with patch.object(ServiceAuthMiddleware, 'app_manager', mock_app_manager):
            middleware = ServiceAuthMiddleware(MagicMock())
            response = await middleware.dispatch(mock_request, mock_call_next)

        assert call_next_called is True
        assert response is expected_response


class TestServiceAuthMiddlewareInterface:
    """Tests for ServiceAuthMiddleware interface compliance."""

    def test_implements_middleware_interface(self):
        """Test that ServiceAuthMiddleware implements MiddlewareInterface."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware
        from lys.core.interfaces.middlewares import MiddlewareInterface

        assert issubclass(ServiceAuthMiddleware, MiddlewareInterface)

    def test_inherits_base_http_middleware(self):
        """Test that ServiceAuthMiddleware inherits from BaseHTTPMiddleware."""
        from lys.apps.base.middlewares import ServiceAuthMiddleware
        from starlette.middleware.base import BaseHTTPMiddleware

        assert issubclass(ServiceAuthMiddleware, BaseHTTPMiddleware)
