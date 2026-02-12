"""
Unit tests for SSOAuthService business logic.

Tests cover:
- Provider config retrieval and validation
- SSO mode validation
- State management (generate_authorize_url stores state in Redis)
- Callback state validation and consumption
- handle_signup stores session in Redis
- get_sso_session reads from Redis
- consume_sso_session atomically reads and deletes
- handle_login returns error URL when link not found
- handle_link creates SSO link

Test approach: Unit (mocked Redis via PubSub, mocked httpx, mocked app_manager)
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lys.apps.sso.consts import SSO_STATE_PREFIX, SSO_SESSION_PREFIX, SSO_SESSION_TTL
from lys.apps.sso.errors import (
    SSO_PROVIDER_NOT_FOUND,
    SSO_INVALID_MODE,
    SSO_INVALID_STATE,
    SSO_CALLBACK_ERROR,
    SSO_INVALID_TOKEN,
    SSO_MISSING_EMAIL,
    SSO_SESSION_EXPIRED,
)
from lys.apps.sso.modules.auth.services import SSOAuthService
from lys.core.errors import LysError

from tests.mocks.utils import configure_classes_for_testing
from tests.mocks.app_manager import MockAppManager


@pytest.fixture
def mock_pubsub():
    """Create a mocked PubSubManager."""
    pubsub = AsyncMock()
    pubsub.set_key = AsyncMock(return_value=True)
    pubsub.get_key = AsyncMock(return_value=None)
    pubsub.get_and_delete_key = AsyncMock(return_value=None)
    pubsub.delete_key = AsyncMock(return_value=True)
    return pubsub


@pytest.fixture
def sso_app_manager(mock_pubsub):
    """Create a mock app_manager configured for SSO tests."""
    mock_app = MockAppManager()
    mock_app.pubsub = mock_pubsub

    # Configure SSO plugin settings
    mock_settings = MagicMock()
    mock_settings.front_url = "https://app.example.com"
    mock_settings.get_plugin_config.return_value = {
        "callback_base_url": "https://api.example.com",
        "signup_path": "/signup",
        "providers": {
            "microsoft": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "issuer_url": "https://login.microsoftonline.com/tenant/v2.0",
                "display_name": "Microsoft",
                "scopes": ["openid", "email", "profile"],
            }
        },
    }
    mock_app.settings = mock_settings

    # Register mock services
    mock_sso_link_service = MagicMock()
    mock_sso_link_service.find_by_provider_and_external_id = AsyncMock(return_value=None)
    mock_sso_link_service.create_link = AsyncMock()
    mock_app.register_service("user_sso_link", mock_sso_link_service)

    mock_user_service = MagicMock()
    mock_user_service.get_by_id = AsyncMock(return_value=None)
    mock_app.register_service("user", mock_user_service)

    mock_auth_service = MagicMock()
    mock_auth_service.generate_access_token = AsyncMock(return_value=("token", {"xsrf_token": "xsrf"}))
    mock_auth_service.set_auth_cookies = AsyncMock()
    mock_app.register_service("auth", mock_auth_service)

    mock_refresh_service = MagicMock()
    mock_refresh_service.generate = AsyncMock()
    mock_app.register_service("user_refresh_token", mock_refresh_service)

    configure_classes_for_testing(mock_app, SSOAuthService)

    return mock_app


class TestProviderConfig:
    """Tests for provider configuration retrieval."""

    def test_get_provider_config_valid(self, sso_app_manager):
        config = SSOAuthService._get_provider_config("microsoft")
        assert config["client_id"] == "test-client-id"

    def test_get_provider_config_unknown_raises(self, sso_app_manager):
        with pytest.raises(LysError) as exc_info:
            SSOAuthService._get_provider_config("unknown_provider")
        assert exc_info.value.detail == SSO_PROVIDER_NOT_FOUND[1]


class TestGenerateAuthorizeUrl:
    """Tests for OAuth2 authorization URL generation."""

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self, sso_app_manager):
        with pytest.raises(LysError) as exc_info:
            await SSOAuthService.generate_authorize_url(
                provider="microsoft",
                mode="invalid_mode",
                callback_url="https://api.example.com/callback",
            )
        assert exc_info.value.detail == SSO_INVALID_MODE[1]

    @pytest.mark.asyncio
    async def test_state_stored_in_redis(self, sso_app_manager, mock_pubsub):
        """Test that state is stored in Redis during authorize URL generation."""
        # Mock the OIDC discovery and OAuth2 client
        mock_discovery = {
            "authorization_endpoint": "https://login.microsoftonline.com/authorize",
        }

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth:

            # Mock discovery response (httpx Response.json() is sync)
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_discovery
            mock_resp.raise_for_status = MagicMock()
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_resp)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = mock_client_instance

            # Mock OAuth2 client
            mock_oauth_instance = MagicMock()
            mock_oauth_instance.create_authorization_url.return_value = (
                "https://login.microsoftonline.com/authorize?state=abc",
                "abc",
            )
            mock_oauth.return_value = mock_oauth_instance

            url = await SSOAuthService.generate_authorize_url(
                provider="microsoft",
                mode="login",
                callback_url="https://api.example.com/callback",
            )

            # Verify state was stored in Redis
            mock_pubsub.set_key.assert_called_once()
            call_args = mock_pubsub.set_key.call_args
            assert call_args[0][0].startswith(SSO_STATE_PREFIX)
            state_data = json.loads(call_args[0][1])
            assert state_data["provider"] == "microsoft"
            assert state_data["mode"] == "login"
            assert "nonce" in state_data

            assert "authorize" in url


class TestHandleCallbackStateValidation:
    """Tests for callback state validation (without full OIDC flow)."""

    @pytest.mark.asyncio
    async def test_invalid_state_raises(self, sso_app_manager, mock_pubsub):
        """State not found in Redis."""
        mock_pubsub.get_and_delete_key.return_value = None

        with pytest.raises(LysError) as exc_info:
            await SSOAuthService.handle_callback(
                provider="microsoft",
                code="auth_code",
                state="invalid-state",
                callback_url="https://api.example.com/callback",
            )
        assert exc_info.value.detail == SSO_INVALID_STATE[1]

    @pytest.mark.asyncio
    async def test_provider_mismatch_raises(self, sso_app_manager, mock_pubsub):
        """State exists but provider doesn't match."""
        mock_pubsub.get_and_delete_key.return_value = json.dumps({
            "provider": "google",
            "mode": "login",
            "nonce": "test-nonce",
        })

        with pytest.raises(LysError) as exc_info:
            await SSOAuthService.handle_callback(
                provider="microsoft",
                code="auth_code",
                state="some-state",
                callback_url="https://api.example.com/callback",
            )
        assert exc_info.value.detail == SSO_INVALID_STATE[1]


class TestHandleSignup:
    """Tests for signup mode handler."""

    @pytest.mark.asyncio
    async def test_stores_session_in_redis(self, sso_app_manager, mock_pubsub):
        user_info = {
            "provider": "microsoft",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "external_user_id": "ext-123",
        }

        redirect_url = await SSOAuthService.handle_signup(user_info)

        # Verify session stored in Redis with TTL
        mock_pubsub.set_key.assert_called_once()
        call_args = mock_pubsub.set_key.call_args
        assert call_args[0][0].startswith(SSO_SESSION_PREFIX)
        session_data = json.loads(call_args[0][1])
        assert session_data["email"] == "user@example.com"
        assert session_data["provider"] == "microsoft"
        assert session_data["external_user_id"] == "ext-123"
        assert call_args[1]["ttl_seconds"] == SSO_SESSION_TTL

    @pytest.mark.asyncio
    async def test_returns_redirect_with_token(self, sso_app_manager, mock_pubsub):
        user_info = {
            "provider": "microsoft",
            "email": "user@example.com",
            "external_user_id": "ext-123",
        }

        redirect_url = await SSOAuthService.handle_signup(user_info)

        assert redirect_url.startswith("https://app.example.com/signup?sso_token=")


class TestSSOSession:
    """Tests for SSO session read/consume."""

    @pytest.mark.asyncio
    async def test_get_sso_session_returns_data(self, sso_app_manager, mock_pubsub):
        session_data = {"email": "user@example.com", "provider": "microsoft"}
        mock_pubsub.get_key.return_value = json.dumps(session_data)

        result = await SSOAuthService.get_sso_session("some-token")

        assert result["email"] == "user@example.com"
        assert result["provider"] == "microsoft"

    @pytest.mark.asyncio
    async def test_get_sso_session_returns_none_when_expired(self, sso_app_manager, mock_pubsub):
        mock_pubsub.get_key.return_value = None

        result = await SSOAuthService.get_sso_session("expired-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_consume_sso_session_returns_data(self, sso_app_manager, mock_pubsub):
        session_data = {"email": "user@example.com", "provider": "microsoft", "external_user_id": "ext-123"}
        mock_pubsub.get_and_delete_key.return_value = json.dumps(session_data)

        result = await SSOAuthService.consume_sso_session("some-token")

        assert result["email"] == "user@example.com"
        mock_pubsub.get_and_delete_key.assert_called_once_with(f"{SSO_SESSION_PREFIX}some-token")

    @pytest.mark.asyncio
    async def test_consume_sso_session_expired_raises(self, sso_app_manager, mock_pubsub):
        mock_pubsub.get_and_delete_key.return_value = None

        with pytest.raises(LysError) as exc_info:
            await SSOAuthService.consume_sso_session("expired-token")
        assert exc_info.value.detail == SSO_SESSION_EXPIRED[1]


class TestHandleLogin:
    """Tests for login mode handler."""

    @pytest.mark.asyncio
    async def test_login_no_link_returns_error_url(self, sso_app_manager):
        """When no SSO link exists, return error redirect."""
        user_info = {
            "provider": "microsoft",
            "external_user_id": "ext-123",
        }
        session = AsyncMock()

        redirect_url = await SSOAuthService.handle_login(user_info, MagicMock(), session)

        assert "error=SSO_USER_NOT_FOUND" in redirect_url

    @pytest.mark.asyncio
    async def test_login_link_exists_but_user_gone(self, sso_app_manager):
        """Link exists but user was deleted."""
        user_info = {
            "provider": "microsoft",
            "external_user_id": "ext-123",
        }
        session = AsyncMock()

        # Mock: link found but user not found
        mock_link = MagicMock()
        mock_link.user_id = "user-123"
        sso_link_service = sso_app_manager.get_service("user_sso_link")
        sso_link_service.find_by_provider_and_external_id.return_value = mock_link
        user_service = sso_app_manager.get_service("user")
        user_service.get_by_id.return_value = None

        redirect_url = await SSOAuthService.handle_login(user_info, MagicMock(), session)

        assert "error=SSO_USER_NOT_FOUND" in redirect_url

    @pytest.mark.asyncio
    async def test_login_success_sets_cookies(self, sso_app_manager):
        """Successful SSO login generates tokens and sets cookies."""
        user_info = {
            "provider": "microsoft",
            "external_user_id": "ext-123",
        }
        session = AsyncMock()
        response = MagicMock()

        # Mock: link and user found
        mock_link = MagicMock()
        mock_link.user_id = "user-123"
        sso_link_service = sso_app_manager.get_service("user_sso_link")
        sso_link_service.find_by_provider_and_external_id.return_value = mock_link

        mock_user = MagicMock()
        mock_user.id = "user-123"
        user_service = sso_app_manager.get_service("user")
        user_service.get_by_id.return_value = mock_user

        mock_refresh_token = MagicMock()
        mock_refresh_token.id = "refresh-token-id"
        refresh_service = sso_app_manager.get_service("user_refresh_token")
        refresh_service.generate.return_value = mock_refresh_token

        redirect_url = await SSOAuthService.handle_login(user_info, response, session)

        # Should return front_url (no error)
        assert redirect_url == "https://app.example.com"
        # Cookies should be set
        auth_service = sso_app_manager.get_service("auth")
        auth_service.set_auth_cookies.assert_called_once()


class TestHandleLink:
    """Tests for link mode handler."""

    @pytest.mark.asyncio
    async def test_link_creates_sso_link(self, sso_app_manager):
        user_info = {
            "provider": "microsoft",
            "external_user_id": "ext-123",
            "email": "user@example.com",
        }
        session = AsyncMock()

        redirect_url = await SSOAuthService.handle_link(user_info, "user-456", session)

        sso_link_service = sso_app_manager.get_service("user_sso_link")
        sso_link_service.create_link.assert_called_once_with(
            user_id="user-456",
            provider="microsoft",
            external_user_id="ext-123",
            external_email="user@example.com",
            session=session,
        )
        assert "sso_linked=microsoft" in redirect_url


def _mock_valid_state(mock_pubsub, provider="microsoft", mode="login", nonce="test-nonce"):
    """Configure mock pubsub to return valid state for handle_callback."""
    mock_pubsub.get_and_delete_key.return_value = json.dumps({
        "provider": provider,
        "mode": mode,
        "nonce": nonce,
    })


def _mock_oidc_flow(
    mock_httpx,
    mock_oauth,
    mock_jwk,
    mock_jwt,
    id_token="fake-id-token",
    discovery_extra=None,
    token_response_extra=None,
    claims=None,
    jwks_uri="https://login.microsoftonline.com/jwks",
):
    """Configure mocks for the full OIDC token exchange flow."""
    discovery = {
        "token_endpoint": "https://login.microsoftonline.com/token",
        "jwks_uri": jwks_uri,
        "issuer": "https://login.microsoftonline.com/tenant/v2.0",
    }
    if discovery_extra:
        discovery.update(discovery_extra)

    token_response = {"id_token": id_token, "access_token": "at-123"}
    if token_response_extra:
        token_response.update(token_response_extra)

    # Mock httpx for discovery + JWKS fetch
    mock_discovery_resp = MagicMock()
    mock_discovery_resp.json.return_value = discovery
    mock_discovery_resp.raise_for_status = MagicMock()

    mock_jwks_resp = MagicMock()
    mock_jwks_resp.json.return_value = {"keys": []}
    mock_jwks_resp.raise_for_status = MagicMock()

    # httpx.AsyncClient used as context manager - called twice (discovery, JWKS)
    call_count = {"n": 0}
    responses = [mock_discovery_resp, mock_jwks_resp]

    mock_http_instance = AsyncMock()

    async def get_side_effect(url):
        resp = responses[call_count["n"]]
        call_count["n"] += 1
        return resp

    mock_http_instance.get = AsyncMock(side_effect=get_side_effect)
    mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
    mock_http_instance.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.return_value = mock_http_instance

    # Mock AsyncOAuth2Client for token exchange
    mock_oauth_instance = AsyncMock()
    mock_oauth_instance.fetch_token = AsyncMock(return_value=token_response)
    mock_oauth_instance.__aenter__ = AsyncMock(return_value=mock_oauth_instance)
    mock_oauth_instance.__aexit__ = AsyncMock(return_value=False)
    mock_oauth.return_value = mock_oauth_instance

    # Mock JWK and JWT
    mock_key_set = MagicMock()
    mock_jwk.import_key_set.return_value = mock_key_set

    default_claims = {
        "iss": "https://login.microsoftonline.com/tenant/v2.0",
        "aud": "test-client-id",
        "sub": "ms-user-001",
        "email": "user@example.com",
        "given_name": "John",
        "family_name": "Doe",
        "nonce": "test-nonce",
    }
    if claims:
        default_claims.update(claims)

    mock_decoded = MagicMock()
    mock_decoded.get.side_effect = lambda key, default="": default_claims.get(key, default)
    mock_decoded.validate = MagicMock()
    mock_jwt.decode.return_value = mock_decoded

    return discovery, token_response, mock_decoded


class TestHandleCallbackOIDCFlow:
    """Tests for handle_callback full OIDC token exchange (lines 158-235)."""

    @pytest.mark.asyncio
    async def test_full_flow_success(self, sso_app_manager, mock_pubsub):
        """Successful OIDC flow: state valid, token exchanged, claims extracted."""
        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt)

            result = await SSOAuthService.handle_callback(
                provider="microsoft",
                code="valid-code",
                state="valid-state",
                callback_url="https://api.example.com/callback",
            )

        assert result["provider"] == "microsoft"
        assert result["mode"] == "login"
        assert result["email"] == "user@example.com"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        assert result["external_user_id"] == "ms-user-001"

    @pytest.mark.asyncio
    async def test_no_id_token_raises(self, sso_app_manager, mock_pubsub):
        """No id_token in provider response raises SSO_CALLBACK_ERROR."""
        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt,
                            id_token=None, token_response_extra={"id_token": None})

            # Override token response to have no id_token
            mock_oauth_instance = mock_oauth.return_value
            mock_oauth_instance.fetch_token.return_value = {"access_token": "at-123"}

            with pytest.raises(LysError) as exc_info:
                await SSOAuthService.handle_callback(
                    provider="microsoft", code="code", state="state",
                    callback_url="https://api.example.com/callback",
                )
            assert exc_info.value.detail == SSO_CALLBACK_ERROR[1]

    @pytest.mark.asyncio
    async def test_no_jwks_uri_raises(self, sso_app_manager, mock_pubsub):
        """Discovery without jwks_uri raises SSO_CALLBACK_ERROR."""
        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt, jwks_uri=None)

            # Override discovery to not have jwks_uri
            mock_http = mock_httpx.return_value
            mock_discovery_resp = MagicMock()
            mock_discovery_resp.json.return_value = {
                "token_endpoint": "https://login.microsoftonline.com/token",
                "issuer": "https://login.microsoftonline.com/tenant/v2.0",
                # No jwks_uri
            }
            mock_discovery_resp.raise_for_status = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_discovery_resp)

            with pytest.raises(LysError) as exc_info:
                await SSOAuthService.handle_callback(
                    provider="microsoft", code="code", state="state",
                    callback_url="https://api.example.com/callback",
                )
            assert exc_info.value.detail == SSO_CALLBACK_ERROR[1]

    @pytest.mark.asyncio
    async def test_invalid_token_signature_raises(self, sso_app_manager, mock_pubsub):
        """JoseError from JWT decode raises SSO_INVALID_TOKEN."""
        from authlib.jose.errors import JoseError

        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt)

            # Make JWT decode raise JoseError
            mock_jwt.decode.side_effect = JoseError("Invalid signature")

            with pytest.raises(LysError) as exc_info:
                await SSOAuthService.handle_callback(
                    provider="microsoft", code="code", state="state",
                    callback_url="https://api.example.com/callback",
                )
            assert exc_info.value.detail == SSO_INVALID_TOKEN[1]

    @pytest.mark.asyncio
    async def test_nonce_mismatch_raises(self, sso_app_manager, mock_pubsub):
        """Token nonce not matching expected nonce raises SSO_INVALID_TOKEN."""
        _mock_valid_state(mock_pubsub, nonce="expected-nonce")

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt,
                            claims={"nonce": "wrong-nonce"})

            with pytest.raises(LysError) as exc_info:
                await SSOAuthService.handle_callback(
                    provider="microsoft", code="code", state="state",
                    callback_url="https://api.example.com/callback",
                )
            assert exc_info.value.detail == SSO_INVALID_TOKEN[1]

    @pytest.mark.asyncio
    async def test_no_email_raises(self, sso_app_manager, mock_pubsub):
        """No email in claims raises SSO_MISSING_EMAIL."""
        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt,
                            claims={"email": "", "preferred_username": ""})

            with pytest.raises(LysError) as exc_info:
                await SSOAuthService.handle_callback(
                    provider="microsoft", code="code", state="state",
                    callback_url="https://api.example.com/callback",
                )
            assert exc_info.value.detail == SSO_MISSING_EMAIL[1]

    @pytest.mark.asyncio
    async def test_email_from_preferred_username_fallback(self, sso_app_manager, mock_pubsub):
        """When email is empty, preferred_username is used as fallback."""
        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt,
                            claims={"email": "", "preferred_username": "user@outlook.com"})

            result = await SSOAuthService.handle_callback(
                provider="microsoft", code="code", state="state",
                callback_url="https://api.example.com/callback",
            )

        assert result["email"] == "user@outlook.com"

    @pytest.mark.asyncio
    async def test_microsoft_oid_used_as_external_id(self, sso_app_manager, mock_pubsub):
        """Microsoft 'oid' claim is preferred over 'sub' for external_user_id."""
        _mock_valid_state(mock_pubsub)

        with patch("lys.apps.sso.modules.auth.services.httpx.AsyncClient") as mock_httpx, \
             patch("lys.apps.sso.modules.auth.services.AsyncOAuth2Client") as mock_oauth, \
             patch("lys.apps.sso.modules.auth.services.JsonWebKey") as mock_jwk, \
             patch("lys.apps.sso.modules.auth.services.authlib_jwt") as mock_jwt:

            _mock_oidc_flow(mock_httpx, mock_oauth, mock_jwk, mock_jwt,
                            claims={"oid": "ms-oid-123", "sub": "ms-sub-456"})

            result = await SSOAuthService.handle_callback(
                provider="microsoft", code="code", state="state",
                callback_url="https://api.example.com/callback",
            )

        assert result["external_user_id"] == "ms-oid-123"
