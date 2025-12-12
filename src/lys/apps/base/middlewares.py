"""
Middlewares for the base app.

This module provides:
- ServiceAuthMiddleware: Service-to-service JWT token validation
"""
import logging
from typing import Dict, Any, Optional

from jwt import ExpiredSignatureError, InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from lys.core.interfaces.middlewares import MiddlewareInterface
from lys.core.utils.auth import AuthUtils
from lys.core.utils.manager import AppManagerCallerMixin


class ServiceAuthMiddleware(MiddlewareInterface, BaseHTTPMiddleware, AppManagerCallerMixin):
    """Middleware for service-to-service JWT authentication.

    This middleware validates JWT tokens from internal service calls and
    injects the service caller context into the request state.

    The token is expected in the Authorization header with the format:
    Authorization: Service <token>
    """

    AUTHORIZATION_PREFIX = "Service "

    def __init__(self, app):
        BaseHTTPMiddleware.__init__(self, app)
        self.auth_utils = AuthUtils(self.app_manager.settings.secret_key)

    async def dispatch(self, request: Request, call_next):
        service_caller: Optional[Dict[str, Any]] = None

        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith(self.AUTHORIZATION_PREFIX):
            token = auth_header[len(self.AUTHORIZATION_PREFIX):]

            try:
                service_caller = self.auth_utils.decode_token(token)
                logging.debug(f"Service {service_caller.get('service_name')} authenticated via JWT")

            except ExpiredSignatureError as e:
                logging.warning(f"Service JWT token expired: {e}")
            except InvalidTokenError as e:
                logging.warning(f"Service JWT validation failed: {e}")
            except Exception as e:
                logging.error(f"Unexpected service JWT validation error: {e}")

        request.state.service_caller = service_caller

        return await call_next(request)