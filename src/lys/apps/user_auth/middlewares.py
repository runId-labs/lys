"""
Authentication middleware for the user_auth app.

This module provides:
- UserAuthMiddleware: User JWT token validation and user context injection
"""
import hmac
import logging
from typing import Union, Dict, Any

from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from lys.apps.user_auth.consts import ACCESS_COOKIE_KEY, AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY, REQUEST_HEADER_XSRF_TOKEN_KEY
from lys.apps.user_auth.errors import INVALID_XSRF_TOKEN_ERROR
from lys.apps.user_auth.utils import AuthUtils
from lys.core.errors import LysError
from lys.core.interfaces.middlewares import MiddlewareInterface


class UserAuthMiddleware(MiddlewareInterface, BaseHTTPMiddleware):
    """User authentication middleware that validates JWT tokens and injects user context."""

    REQUIRED_JWT_CLAIMS = ["sub", "exp", "xsrf_token"]

    def __init__(self, app):
        BaseHTTPMiddleware.__init__(self, app)
        self.auth_utils = AuthUtils()

    async def dispatch(self, request: Request, call_next):
        # Initialize default user context
        connected_user: Union[Dict[str, Any], None] = None

        # Extract access token from cookies (browser) or Authorization header (API calls)
        # Priority: cookie first, then header fallback
        # Security note: The refresh token cookie is deliberately NOT extracted here
        # even though it is sent with every request (path="/")
        # Refresh token is only used in specific auth operations (login, logout, refresh)
        # This provides defense-in-depth security
        access_token = request.cookies.get(ACCESS_COOKIE_KEY)
        token_from_header = False

        # Fallback to Authorization header for API/service calls
        if not access_token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                access_token = auth_header[7:]
                token_from_header = True

        if access_token:
            try:
                # Use centralized JWT decoding logic
                jwt_claims = await self.auth_utils.decode(access_token)

                # Validate required JWT claims
                missing_claims = [claim for claim in self.REQUIRED_JWT_CLAIMS if claim not in jwt_claims]
                if missing_claims:
                    logging.error(f"Missing required JWT claims: {missing_claims}")
                    jwt_claims = None

            except ExpiredSignatureError as e:
                logging.warning(f"JWT token expired: {e}")
                jwt_claims = None
            except (InvalidTokenError, DecodeError) as e:
                logging.warning(f"JWT validation failed: {e}")
                jwt_claims = None
            except Exception as e:
                logging.error(f"Unexpected JWT validation error: {e}")
                jwt_claims = None

            # Validate JWT and XSRF token if present
            # Skip XSRF validation for Bearer header auth (API/service calls)
            # XSRF protection is only needed for cookie-based auth (browser requests)
            if jwt_claims:
                try:
                    if not token_from_header and self.auth_utils.config.get(AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY, True):
                        xsrf_token = request.headers.get(REQUEST_HEADER_XSRF_TOKEN_KEY)
                        if not xsrf_token:
                            logging.error("XSRF token missing in request headers")
                            raise LysError(INVALID_XSRF_TOKEN_ERROR, "XSRF token missing")

                        expected_xsrf = jwt_claims.get("xsrf_token")
                        if not expected_xsrf:
                            logging.error("XSRF token missing in JWT claims")
                            raise LysError(INVALID_XSRF_TOKEN_ERROR, "XSRF token not found in JWT")

                        if not hmac.compare_digest(xsrf_token, expected_xsrf):
                            logging.error(f"XSRF token mismatch: got '{xsrf_token}', expected '{expected_xsrf}'")
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

                # Create an authenticated user context with all JWT claims at root level
                connected_user = jwt_claims
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
            logging.error(f"Request processing failed for user {connected_user['sub']}: {e}")
            raise