"""
Unit tests for SSO REST endpoints (router-level).

Tests cover:
- sso_login: redirect to provider, error handling
- sso_callback: error param handling (provider cancelled), state validation errors
- sso_callback: signup mode redirect
- sso_callback: link mode without auth

Test approach: Unit (FastAPI TestClient with mocked LysAppManager singleton)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lys.apps.sso.modules.auth.webservices import router
from lys.core.errors import LysError
from lys.apps.sso.errors import SSO_INVALID_STATE, SSO_INVALID_MODE


def _create_test_app():
    """Create a minimal FastAPI app with SSO router."""
    app = FastAPI()
    app.include_router(router)
    return app


def _mock_app_manager():
    """Create a mock LysAppManager for endpoint tests."""
    mock = MagicMock()
    mock.settings.front_url = "https://app.example.com"

    mock_sso_service = MagicMock()
    mock_sso_service.generate_authorize_url = AsyncMock(
        return_value="https://provider.com/authorize?state=abc"
    )
    mock_sso_service.handle_callback = AsyncMock()
    mock_sso_service.handle_login = AsyncMock()
    mock_sso_service.handle_signup = AsyncMock(
        return_value="https://app.example.com/signup?sso_token=tok-123"
    )
    mock_sso_service.handle_link = AsyncMock()
    mock.get_service.return_value = mock_sso_service

    mock.database = MagicMock()
    mock_session = AsyncMock()
    mock.database.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock.database.get_session.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock, mock_sso_service


class TestSSOLoginEndpoint:
    """Tests for GET /auth/sso/{provider}/login."""

    @pytest.mark.asyncio
    async def test_login_redirects_to_provider(self):
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/auth/sso/microsoft/login", follow_redirects=False)

        assert resp.status_code == 302
        assert resp.headers["location"] == "https://provider.com/authorize?state=abc"

    @pytest.mark.asyncio
    async def test_login_error_redirects_to_frontend(self):
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.generate_authorize_url = AsyncMock(
            side_effect=Exception("Connection error")
        )

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/auth/sso/microsoft/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "error=SSO_CALLBACK_ERROR" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_login_invalid_mode_raises(self):
        """Invalid mode query param raises LysError (line 29)."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/login?mode=invalid_mode",
                    follow_redirects=False,
                )

        # LysError from invalid mode results in 400
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_login_lys_error_redirects_with_error_code(self):
        """LysError in generate_authorize_url redirects with error code (lines 47-50)."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.generate_authorize_url = AsyncMock(
            side_effect=LysError(SSO_INVALID_MODE, "Provider not found")
        )

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/auth/sso/microsoft/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "error=SSO_INVALID_MODE" in resp.headers["location"]


class TestSSOCallbackEndpoint:
    """Tests for GET /auth/sso/{provider}/callback."""

    @pytest.mark.asyncio
    async def test_callback_with_error_param_redirects(self):
        """When provider sends error param (user cancelled), redirect gracefully."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?error=access_denied&error_description=User+cancelled",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert "error=SSO_CALLBACK_ERROR" in resp.headers["location"]
        # Should NOT call handle_callback (early return)
        mock_sso.handle_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_callback_invalid_state_redirects(self):
        """When state is invalid, redirect to frontend with error."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(
            side_effect=LysError(SSO_INVALID_STATE, "Invalid state")
        )

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=abc&state=invalid",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert "error=" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_signup_mode_redirects_with_token(self):
        """Signup mode returns redirect with sso_token."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(return_value={
            "provider": "microsoft",
            "mode": "signup",
            "email": "user@test.com",
            "first_name": "John",
            "last_name": "Doe",
            "external_user_id": "ext-123",
        })

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=valid&state=valid",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert "sso_token=tok-123" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_link_mode_without_auth_redirects_error(self):
        """Link mode without access token cookie returns error."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(return_value={
            "provider": "microsoft",
            "mode": "link",
            "email": "user@test.com",
            "external_user_id": "ext-123",
        })

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=valid&state=valid",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert "error=SSO_NOT_AUTHENTICATED" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_unexpected_error_redirects(self):
        """Unexpected exceptions redirect gracefully."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(
            side_effect=RuntimeError("Unexpected")
        )

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=abc&state=xyz",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert "error=SSO_CALLBACK_ERROR" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_login_mode_success(self):
        """Login mode: handle_login returns front_url, response keeps cookies (lines 90-96)."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(return_value={
            "provider": "microsoft",
            "mode": "login",
            "email": "user@test.com",
            "external_user_id": "ext-123",
        })
        mock_sso.handle_login = AsyncMock(return_value="https://app.example.com")

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=valid&state=valid",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert resp.headers["location"] == "https://app.example.com"
        mock_sso.handle_login.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_login_mode_user_not_found(self):
        """Login mode: user not found redirects to error URL (lines 94-96)."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(return_value={
            "provider": "microsoft",
            "mode": "login",
            "email": "user@test.com",
            "external_user_id": "ext-123",
        })
        mock_sso.handle_login = AsyncMock(
            return_value="https://app.example.com?error=SSO_USER_NOT_FOUND"
        )

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=valid&state=valid",
                    follow_redirects=False,
                )

        assert resp.status_code == 302
        assert "error=SSO_USER_NOT_FOUND" in resp.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_link_mode_with_auth_success(self):
        """Link mode with valid access token cookie creates link (lines 108-115)."""
        app = _create_test_app()
        mock_am, mock_sso = _mock_app_manager()
        mock_sso.handle_callback = AsyncMock(return_value={
            "provider": "microsoft",
            "mode": "link",
            "email": "user@test.com",
            "external_user_id": "ext-123",
        })
        mock_sso.handle_link = AsyncMock(
            return_value="https://app.example.com/settings?sso_linked=microsoft"
        )

        with patch("lys.apps.sso.modules.auth.webservices.LysAppManager", return_value=mock_am), \
             patch("lys.apps.sso.modules.auth.webservices.AuthUtils") as mock_auth_utils:

            mock_auth_instance = MagicMock()
            mock_auth_instance.decode = AsyncMock(return_value={"sub": "user-456"})
            mock_auth_utils.return_value = mock_auth_instance

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/auth/sso/microsoft/callback?code=valid&state=valid",
                    follow_redirects=False,
                    cookies={"access_token": "valid-jwt-token"},
                )

        assert resp.status_code == 302
        assert "sso_linked=microsoft" in resp.headers["location"]
        mock_sso.handle_link.assert_called_once()
