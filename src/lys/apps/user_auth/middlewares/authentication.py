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


class JWTAuthMiddleware(MiddlewareInterface, BaseHTTPMiddleware):
    REQUIRED_JWT_CLAIMS = ["user", "exp", "xsrf_token"]

    def __init__(self, app):
        BaseHTTPMiddleware.__init__(self, app)
        self.auth_utils = AuthUtils()

    async def dispatch(self, request: Request, call_next):
        # Initialize default user context
        connected_user: Union[Dict[str, Any], None] = None

        # Extract ONLY the access token from cookies
        # Security note: The refresh token cookie is deliberately NOT extracted here
        # even though it is sent with every request (path="/")
        # Refresh token is only used in specific auth operations (login, logout, refresh)
        # This provides defense-in-depth security
        access_token = request.cookies.get(ACCESS_COOKIE_KEY)

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
            if jwt_claims:
                try:
                    if self.auth_utils.config.get(AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY):
                        xsrf_token = request.headers.get(REQUEST_HEADER_XSRF_TOKEN_KEY)
                        if not xsrf_token:
                            logging.error("XSRF token missing in request headers")
                            raise LysError(INVALID_XSRF_TOKEN_ERROR, "XSRF token missing")

                        expected_xsrf = jwt_claims.get("xsrf_token")
                        if not expected_xsrf:
                            logging.error("XSRF token missing in JWT claims")
                            raise LysError(INVALID_XSRF_TOKEN_ERROR, "XSRF token not found in JWT")

                        if xsrf_token != expected_xsrf:
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

                # Create an authenticated user context
                connected_user = jwt_claims["user"]
                logging.debug(f"User {connected_user["id"]} authenticated via JWT")
            else:
                logging.debug("No valid JWT token - user remains anonymous")

        # Inject user context into request state
        request.state.connected_user = connected_user

        # Process request with error handling
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logging.error(f"Request processing failed for user {connected_user['id']}: {e}")
            raise
