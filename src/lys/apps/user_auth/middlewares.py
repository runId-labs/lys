"""
Authentication middleware for the user_auth app.

This module provides:
- UserAuthMiddleware: Opaque access token resolution and user context injection.

The middleware looks up the access token (from the cookie or an
``Authorization: Bearer`` header) in the server-side store
(``AccessTokenStore``) instead of decoding a JWT. This keeps the cookie
small (~36 bytes UUID) and avoids the RFC 6265 4096-byte cookie limit
that broke logins for users with broad permissions when claims were
embedded inline in a JWT.

XSRF semantics are unchanged: the ``xsrf_token`` claim still lives in
the claims dict (now stored server-side); the middleware compares it to
the ``x-xsrf-token`` header on state-changing cookie requests.
"""
import hmac
import logging
from typing import Union, Dict, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from lys.apps.user_auth.consts import ACCESS_COOKIE_KEY, AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY, REQUEST_HEADER_XSRF_TOKEN_KEY
from lys.apps.user_auth.errors import INVALID_XSRF_TOKEN_ERROR
from lys.apps.user_auth.modules.auth.store import AccessTokenStore
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.interfaces.middlewares import MiddlewareInterface
from lys.core.utils.manager import AppManagerCallerMixin


class UserAuthMiddleware(MiddlewareInterface, BaseHTTPMiddleware, AppManagerCallerMixin):
    """User authentication middleware that resolves opaque access tokens and injects user context."""

    REQUIRED_CLAIMS = ["sub", "exp", "xsrf_token"]

    def __init__(self, app):
        BaseHTTPMiddleware.__init__(self, app)
        # AuthUtils is kept for cookie/XSRF config access (cookie_secure,
        # check_xsrf_token, …). It no longer encodes/decodes user JWTs.
        self.auth_utils = AuthUtils()

    def _build_store(self) -> Union[AccessTokenStore, None]:
        """
        Build an AccessTokenStore bound to the current app_manager pubsub.

        Returns None when pubsub is not initialised — the dispatch loop
        treats this the same as "no token", which means unauthenticated.
        Logged at warning level because in normal operation the lifespan
        always initialises pubsub before requests are accepted.
        """
        pubsub = getattr(self.app_manager, "pubsub", None)
        if pubsub is None:
            logging.warning(
                "UserAuthMiddleware: PubSubManager unavailable — treating request as anonymous. "
                "Ensure the 'pubsub' plugin is configured."
            )
            return None
        return AccessTokenStore(pubsub)

    async def dispatch(self, request: Request, call_next):
        # Initialize default user context
        connected_user: Union[Dict[str, Any], None] = None

        # Extract opaque access token from cookies (browser) or Authorization header (API/service calls).
        # Priority: cookie first, then header fallback.
        # Security note: The refresh token cookie is deliberately NOT extracted here
        # even though it is sent with every request (path="/").
        # Refresh token is only used in specific auth operations (login, logout, refresh).
        access_token = request.cookies.get(ACCESS_COOKIE_KEY)
        token_from_header = False

        # Fallback to Authorization header for API/service calls
        if not access_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                access_token = auth_header[7:]
                token_from_header = True

        claims: Union[Dict[str, Any], None] = None

        if access_token:
            store = self._build_store()
            if store is not None:
                try:
                    claims = await store.get(access_token)
                except Exception as e:
                    # Storage failure (Redis down, decode error). Treat as
                    # anonymous to avoid leaking infra issues as auth errors.
                    logging.error(f"AccessTokenStore lookup failed: {e}")
                    claims = None

            if claims is None:
                # Token absent from the store: expired (TTL elapsed),
                # revoked (logout/refresh), or never issued. Same outcome
                # as a previously expired JWT.
                logging.info("Access token not found in store (expired, revoked, or unknown)")
            else:
                missing_claims = [c for c in self.REQUIRED_CLAIMS if c not in claims]
                if missing_claims:
                    logging.error(f"Stored access token claims missing required fields: {missing_claims}")
                    claims = None

            # Validate XSRF token if claims resolved.
            # Skip XSRF validation for:
            # - Bearer header auth (API/service calls)
            # - Safe HTTP methods (GET, HEAD, OPTIONS) per RFC 7231
            #   CSRF targets state-changing requests; safe methods are read-only.
            #   This also allows EventSource/SSE which only supports GET with cookies.
            if claims:
                try:
                    is_safe_method = request.method in ("GET", "HEAD", "OPTIONS")
                    if not token_from_header and not is_safe_method and self.auth_utils.config.get(AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY, True):
                        xsrf_token = request.headers.get(REQUEST_HEADER_XSRF_TOKEN_KEY)
                        if not xsrf_token:
                            logging.error("XSRF token missing in request headers")
                            raise LysError(INVALID_XSRF_TOKEN_ERROR, "XSRF token missing")

                        expected_xsrf = claims.get("xsrf_token")
                        if not expected_xsrf:
                            logging.error("XSRF token missing in stored claims")
                            raise LysError(INVALID_XSRF_TOKEN_ERROR, "XSRF token not found in stored claims")

                        if not hmac.compare_digest(xsrf_token, expected_xsrf):
                            logging.error("XSRF token mismatch")
                            raise LysError(
                                INVALID_XSRF_TOKEN_ERROR,
                                f"XSRF token mismatch: got '{xsrf_token}', expected '{expected_xsrf}'"
                            )

                except LysError:
                    # Re-raise LysError as-is
                    raise
                except Exception as ex:
                    logging.error(f"XSRF validation error: {ex}")
                    raise LysError(INVALID_XSRF_TOKEN_ERROR, f"XSRF validation failed: {str(ex)}")

                # Surface the resolved claims as the connected user (same contract as before).
                connected_user = claims
                auth_source = "header" if token_from_header else "cookie"
                logging.info(f"User {connected_user['sub']} authenticated via {auth_source}")

        # Inject user context and original token into request state
        request.state.connected_user = connected_user
        request.state.access_token = access_token if connected_user else None

        # Process request with error handling
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            user_id = connected_user["sub"] if connected_user else None
            logging.error(f"Request processing failed for user {user_id}: {e}")
            raise
