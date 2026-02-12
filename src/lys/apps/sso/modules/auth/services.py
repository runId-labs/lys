import json
import logging
import uuid
from typing import Optional

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, jwt as authlib_jwt
from authlib.jose.errors import JoseError
from starlette.responses import Response

from lys.apps.sso.consts import (
    SSO_PLUGIN_KEY,
    SSO_STATE_PREFIX,
    SSO_SESSION_PREFIX,
    SSO_STATE_TTL,
    SSO_SESSION_TTL,
    VALID_SSO_MODES,
)
from lys.apps.sso.errors import (
    SSO_PROVIDER_NOT_FOUND,
    SSO_INVALID_STATE,
    SSO_INVALID_MODE,
    SSO_CALLBACK_ERROR,
    SSO_INVALID_TOKEN,
    SSO_MISSING_EMAIL,
    SSO_SESSION_EXPIRED,
)
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import Service

logger = logging.getLogger(__name__)


@register_service()
class SSOAuthService(Service):
    """Service handling OAuth2/OIDC authorization code flow for SSO."""

    service_name = "sso_auth"

    @classmethod
    def _get_sso_config(cls) -> dict:
        """Get the SSO plugin configuration."""
        return cls.app_manager.settings.get_plugin_config(SSO_PLUGIN_KEY)

    @classmethod
    def _get_provider_config(cls, provider: str) -> dict:
        """Get configuration for a specific SSO provider."""
        sso_config = cls._get_sso_config()
        providers = sso_config.get("providers", {})
        if provider not in providers:
            raise LysError(SSO_PROVIDER_NOT_FOUND, f"SSO provider '{provider}' is not configured")
        return providers[provider]

    @classmethod
    def _get_pubsub(cls):
        """Get the PubSubManager for Redis operations."""
        return cls.app_manager.pubsub

    # ==================== OAuth2 Flow ====================

    @classmethod
    async def generate_authorize_url(
        cls,
        provider: str,
        mode: str,
        callback_url: str,
    ) -> str:
        """
        Generate the OAuth2 authorization URL and store state in Redis.

        Args:
            provider: SSO provider identifier (e.g. "microsoft")
            mode: SSO mode ("login", "signup", "link")
            callback_url: The callback URL for the provider to redirect to

        Returns:
            The authorization URL to redirect the user to
        """
        if mode not in VALID_SSO_MODES:
            raise LysError(SSO_INVALID_MODE, f"Invalid SSO mode '{mode}'. Must be one of: {VALID_SSO_MODES}")

        provider_config = cls._get_provider_config(provider)
        pubsub = cls._get_pubsub()

        # Generate state and nonce
        state = str(uuid.uuid4())
        nonce = str(uuid.uuid4())

        # Store state in Redis with mode and nonce
        state_data = json.dumps({
            "provider": provider,
            "mode": mode,
            "nonce": nonce,
        })
        await pubsub.set_key(f"{SSO_STATE_PREFIX}{state}", state_data, ttl_seconds=SSO_STATE_TTL)

        # Discover OIDC endpoints
        issuer_url = provider_config["issuer_url"]
        discovery_url = f"{issuer_url}/.well-known/openid-configuration"

        async with httpx.AsyncClient() as http_client:
            discovery_resp = await http_client.get(discovery_url)
            discovery_resp.raise_for_status()
            discovery = discovery_resp.json()
            authorization_endpoint = discovery["authorization_endpoint"]

        # Build authorization URL
        client = AsyncOAuth2Client(
            client_id=provider_config["client_id"],
            client_secret=provider_config["client_secret"],
            scope=" ".join(provider_config.get("scopes", ["openid", "email", "profile"])),
            redirect_uri=callback_url,
        )
        url, _ = client.create_authorization_url(
            authorization_endpoint,
            state=state,
            nonce=nonce,
            response_type="code",
        )

        return url

    @classmethod
    async def handle_callback(
        cls,
        provider: str,
        code: str,
        state: str,
        callback_url: str,
    ) -> dict:
        """
        Handle the OAuth2 callback: validate state, exchange code for tokens, extract user info.

        Args:
            provider: SSO provider identifier
            code: Authorization code from the provider
            state: State parameter from the callback
            callback_url: The callback URL used in the original request

        Returns:
            Dict with keys: provider, mode, email, first_name, last_name, external_user_id
        """
        pubsub = cls._get_pubsub()

        # Atomically validate and consume state from Redis
        state_key = f"{SSO_STATE_PREFIX}{state}"
        state_json = await pubsub.get_and_delete_key(state_key)
        if not state_json:
            raise LysError(SSO_INVALID_STATE, "Invalid or expired SSO state")

        state_data = json.loads(state_json)

        if state_data["provider"] != provider:
            raise LysError(SSO_INVALID_STATE, "SSO state provider mismatch")

        mode = state_data["mode"]
        nonce = state_data["nonce"]

        # Get provider config and discover endpoints
        provider_config = cls._get_provider_config(provider)
        issuer_url = provider_config["issuer_url"]
        discovery_url = f"{issuer_url}/.well-known/openid-configuration"

        # Fetch OIDC discovery document
        async with httpx.AsyncClient() as http_client:
            discovery_resp = await http_client.get(discovery_url)
            discovery_resp.raise_for_status()
            discovery = discovery_resp.json()
            token_endpoint = discovery["token_endpoint"]

        # Exchange code for tokens
        async with AsyncOAuth2Client(
            client_id=provider_config["client_id"],
            client_secret=provider_config["client_secret"],
            redirect_uri=callback_url,
        ) as client:
            token_response = await client.fetch_token(
                token_endpoint,
                code=code,
                grant_type="authorization_code",
            )

        # Extract user info from ID token claims
        id_token = token_response.get("id_token")
        if not id_token:
            raise LysError(SSO_CALLBACK_ERROR, "No ID token in provider response")

        # Fetch provider JWKS for ID token signature verification
        jwks_uri = discovery.get("jwks_uri")
        if not jwks_uri:
            raise LysError(SSO_CALLBACK_ERROR, "No jwks_uri in provider discovery document")

        async with httpx.AsyncClient() as http_client:
            jwks_resp = await http_client.get(jwks_uri)
            jwks_resp.raise_for_status()
            jwks = jwks_resp.json()

        # Decode and verify ID token with provider's public keys
        canonical_issuer = discovery.get("issuer", issuer_url)
        try:
            key_set = JsonWebKey.import_key_set(jwks)
            claims = authlib_jwt.decode(
                id_token,
                key_set,
                claims_options={
                    "iss": {"essential": True, "value": canonical_issuer},
                    "aud": {"essential": True, "value": provider_config["client_id"]},
                },
            )
            claims.validate()
        except JoseError as e:
            raise LysError(SSO_INVALID_TOKEN, f"ID token validation failed: {e}") from e

        # Verify nonce to prevent replay attacks
        token_nonce = claims.get("nonce")
        if token_nonce != nonce:
            raise LysError(SSO_INVALID_TOKEN, "ID token nonce does not match expected value")

        # Extract user info from claims
        # Microsoft uses "oid" for user ID, standard OIDC uses "sub"
        external_user_id = claims.get("oid") or claims.get("sub", "")
        email = claims.get("email", "")
        first_name = claims.get("given_name")
        last_name = claims.get("family_name")

        if not email:
            # Try preferred_username as fallback (Microsoft sometimes puts email there)
            email = claims.get("preferred_username", "")

        if not email:
            raise LysError(SSO_MISSING_EMAIL, "SSO provider did not return an email address")

        return {
            "provider": provider,
            "mode": mode,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "external_user_id": external_user_id,
        }

    # ==================== Mode Handlers ====================

    @classmethod
    async def handle_login(
        cls,
        user_info: dict,
        response: Response,
        session,
    ) -> str:
        """
        Handle SSO login mode: find user by SSO link, set auth cookies.

        Only matches users by their existing SSO link (provider + external_user_id).
        Users without a prior SSO link must use the "link" mode while authenticated.

        Returns:
            Redirect URL for the frontend
        """
        front_url = cls.app_manager.settings.front_url
        provider = user_info["provider"]
        external_user_id = user_info["external_user_id"]

        sso_link_service = cls.app_manager.get_service("user_sso_link")
        user_service = cls.app_manager.get_service("user")
        auth_service = cls.app_manager.get_service("auth")
        refresh_token_service = cls.app_manager.get_service("user_refresh_token")

        # Find user by SSO link only (no auto-link by email to prevent account takeover)
        link = await sso_link_service.find_by_provider_and_external_id(provider, external_user_id, session)
        if not link:
            return f"{front_url}?error=SSO_USER_NOT_FOUND"

        user = await user_service.get_by_id(link.user_id, session)
        if not user:
            return f"{front_url}?error=SSO_USER_NOT_FOUND"

        # Generate tokens and set cookies
        refresh_token = await refresh_token_service.generate(user, session=session)
        access_token, claims = await auth_service.generate_access_token(user, session)
        await auth_service.set_auth_cookies(response, refresh_token.id, access_token, claims.get("xsrf_token"))

        return front_url

    @classmethod
    async def handle_signup(
        cls,
        user_info: dict,
    ) -> str:
        """
        Handle SSO signup mode: store session data in Redis, return redirect URL with token.

        Returns:
            Redirect URL with sso_token query parameter
        """
        front_url = cls.app_manager.settings.front_url
        pubsub = cls._get_pubsub()

        # Generate session token and store user info
        sso_token = str(uuid.uuid4())
        session_data = json.dumps({
            "provider": user_info["provider"],
            "email": user_info["email"],
            "first_name": user_info.get("first_name"),
            "last_name": user_info.get("last_name"),
            "external_user_id": user_info["external_user_id"],
        })
        await pubsub.set_key(f"{SSO_SESSION_PREFIX}{sso_token}", session_data, ttl_seconds=SSO_SESSION_TTL)

        sso_config = cls._get_sso_config()
        signup_path = sso_config.get("signup_path", "")
        return f"{front_url.rstrip('/')}{signup_path}?sso_token={sso_token}"

    @classmethod
    async def handle_link(
        cls,
        user_info: dict,
        connected_user_id: str,
        session,
    ) -> str:
        """
        Handle SSO link mode: create SSO link for authenticated user.

        Returns:
            Redirect URL for the frontend
        """
        front_url = cls.app_manager.settings.front_url
        sso_link_service = cls.app_manager.get_service("user_sso_link")

        await sso_link_service.create_link(
            user_id=connected_user_id,
            provider=user_info["provider"],
            external_user_id=user_info["external_user_id"],
            external_email=user_info["email"],
            session=session,
        )

        logger.info(f"User {connected_user_id} linked SSO provider '{user_info['provider']}'")
        return f"{front_url}/settings?sso_linked={user_info['provider']}"

    # ==================== SSO Session (for signup) ====================

    @classmethod
    async def get_sso_session(cls, token: str) -> Optional[dict]:
        """
        Read SSO session data from Redis (non-destructive).

        Args:
            token: The SSO session token

        Returns:
            Session data dict or None if expired/not found
        """
        pubsub = cls._get_pubsub()
        session_json = await pubsub.get_key(f"{SSO_SESSION_PREFIX}{token}")
        if not session_json:
            return None
        return json.loads(session_json)

    @classmethod
    async def consume_sso_session(cls, token: str) -> dict:
        """
        Atomically read and delete SSO session data from Redis.

        Args:
            token: The SSO session token

        Returns:
            Session data dict

        Raises:
            LysError: If session is expired or not found
        """
        pubsub = cls._get_pubsub()
        key = f"{SSO_SESSION_PREFIX}{token}"
        session_json = await pubsub.get_and_delete_key(key)
        if not session_json:
            raise LysError(SSO_SESSION_EXPIRED, "SSO session has expired or is invalid")

        return json.loads(session_json)