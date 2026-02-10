"""
Core middlewares for the lys framework.

This module provides:
- SecurityHeadersMiddleware: Adds standard HTTP security headers
- RateLimitMiddleware: Global API rate limiting (Redis or in-memory)
- LysCorsMiddleware: CORS middleware with plugin configuration
- ErrorManagerMiddleware: Error handling and logging middleware
"""
import logging
import os
import sys
import time
import traceback
from typing import List, Union, Dict, Any

from fastapi import FastAPI, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from lys.apps.base.consts import (
    CORS_PLUGIN_KEY,
    CORS_PLUGIN_ALLOW_ORIGINS_KEY,
    CORS_PLUGIN_ALLOW_METHODS_KEY,
    CORS_PLUGIN_ALLOW_HEADERS_KEY,
    CORS_PLUGIN_ALLOW_CREDENTIALS_KEY,
)
from lys.core.consts.environments import EnvironmentEnum
from lys.core.consts.plugins import RATE_LIMIT_PLUGIN_KEY
from lys.core.consts.tablenames import LOG_TABLENAME
from lys.core.errors import LysError
from lys.core.interfaces.middlewares import MiddlewareInterface
from lys.core.interfaces.services import EntityServiceInterface
from lys.core.utils.manager import AppManagerCallerMixin


class SecurityHeadersMiddleware(MiddlewareInterface, BaseHTTPMiddleware):
    """Adds standard HTTP security headers to all responses.

    Headers applied:
    - X-Content-Type-Options: nosniff (prevents MIME sniffing)
    - X-Frame-Options: DENY (prevents clickjacking)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: disables camera, microphone, geolocation
    - Strict-Transport-Security: HSTS on HTTPS requests (1 year, includeSubDomains)
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


logger = logging.getLogger(__name__)


class RateLimitMiddleware(MiddlewareInterface, AppManagerCallerMixin, BaseHTTPMiddleware):
    """Global API rate limiting middleware.

    Uses Redis (via app_manager.pubsub) if available for distributed rate limiting
    across multiple instances. Falls back to in-memory storage for single-instance
    deployments or when Redis is not configured.

    Configuration via settings.plugins["rate_limit"]:
        - requests_per_minute: Max requests per IP per minute (default: 60)
        - enabled: Enable/disable rate limiting (default: True)
    """

    def __init__(self, app):
        BaseHTTPMiddleware.__init__(self, app)

        config = self.app_manager.settings.plugins.get(RATE_LIMIT_PLUGIN_KEY, {})
        self.requests_per_minute: int = config.get("requests_per_minute", 60)
        self.service_requests_per_minute: int = config.get("service_requests_per_minute", 600)
        self.enabled: bool = config.get("enabled", True)

        # In-memory fallback: {ip: [timestamp, ...]}
        self._memory_store: dict[str, list[float]] = {}

    def _get_redis(self):
        """Get async Redis client from pubsub if available."""
        pubsub = self.app_manager.pubsub
        if pubsub and pubsub._async_redis:
            return pubsub._async_redis
        return None

    async def _check_rate_limit_redis(
        self, client_ip: str, redis_client, limit: int, key_prefix: str = "rate_limit"
    ) -> bool:
        """Check rate limit using Redis INCR + EXPIRE (fixed window).

        Returns True if request is allowed, False if rate limited.
        """
        key = f"{key_prefix}:{client_ip}"
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, 60)
            return count <= limit
        except Exception as e:
            logger.warning("Redis rate limit check failed, allowing request: %s", e)
            return True

    def _check_rate_limit_memory(
        self, client_ip: str, limit: int, key_prefix: str = "rate_limit"
    ) -> bool:
        """Check rate limit using in-memory storage (fixed window).

        Returns True if request is allowed, False if rate limited.
        """
        now = time.time()
        window_start = now - 60

        key = f"{key_prefix}:{client_ip}"
        timestamps = self._memory_store.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= limit:
            self._memory_store[key] = timestamps
            return False

        timestamps.append(now)
        self._memory_store[key] = timestamps
        return True

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Service-to-service calls get a separate, higher rate limit bucket.
        # The token is NOT validated here (ServiceAuthMiddleware handles that),
        # so we still rate-limit to prevent abuse via forged headers.
        auth_header = request.headers.get("Authorization", "")
        is_service_call = auth_header.startswith("Service ")
        rate_limit = self.service_requests_per_minute if is_service_call else self.requests_per_minute
        key_prefix = "rate_limit_svc" if is_service_call else "rate_limit"

        redis_client = self._get_redis()
        if redis_client:
            allowed = await self._check_rate_limit_redis(client_ip, redis_client, rate_limit, key_prefix)
        else:
            allowed = self._check_rate_limit_memory(client_ip, rate_limit, key_prefix)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": "60"}
            )

        return await call_next(request)


class LysCorsMiddleware(MiddlewareInterface, AppManagerCallerMixin, CORSMiddleware):
    """CORS middleware with configuration from plugins."""

    def __init__(self, app: FastAPI):
        self.config: dict[str, Any] = self.app_manager.settings.plugins.get(CORS_PLUGIN_KEY, {})

        CORSMiddleware.__init__(
            self,
            app,
            allow_origins=self.config.get(CORS_PLUGIN_ALLOW_ORIGINS_KEY, ()),
            allow_methods=self.config.get(CORS_PLUGIN_ALLOW_METHODS_KEY, ("GET",)),
            allow_headers=self.config.get(CORS_PLUGIN_ALLOW_HEADERS_KEY, ()),
            allow_credentials=self.config.get(CORS_PLUGIN_ALLOW_CREDENTIALS_KEY, False),
        )


class _MiddlewareLysError(AppManagerCallerMixin, HTTPException):
    """Internal error class for middleware error handling."""

    def __init__(
            self,
            code: int,
            message: str,
            debug_message: str,
            file_name: str,
            line: int,
            traceback_,
            public_extensions: dict | None = None
    ) -> None:
        self.debug_message = debug_message
        self.file_name = file_name
        self.line = line
        self.traceback = traceback_

        # Initialize extensions with public data (always visible)
        self.extensions = public_extensions or {}

        # Add debug info only in DEV environment
        if self.app_manager.settings.env == EnvironmentEnum.DEV:
            self.extensions.update({
                "debug_message": self.debug_message,
                "file_name": self.file_name,
                "line": self.line,
                "traceback": self.traceback
            })

        HTTPException.__init__(
            self,
            status_code=code,
            detail=message
        )

    async def save_error_in_database(self, context: Union[Dict[str, Any], None] = None) -> None:
        log_service: EntityServiceInterface | None = self.app_manager.registry.services.get(LOG_TABLENAME)

        if log_service is not None:
            async with self.app_manager.database.get_session() as session:
                await log_service.create(
                    session,
                    message=self.debug_message,
                    file_name=self.file_name,
                    line=self.line,
                    traceback=self.traceback,
                    context=context
                )


class ErrorManagerMiddleware(MiddlewareInterface, BaseHTTPMiddleware):
    """Error handling middleware that catches and logs exceptions."""

    def __init__(self, app, saved_context_keys: List[str] = None):
        BaseHTTPMiddleware.__init__(self, app)

        if saved_context_keys is None:
            self.saved_context_keys = [
                "access_type",
                "connected_user",
                "webservice_name",
                "webservice_parameters"
            ]
        else:
            self.saved_context_keys = saved_context_keys

    async def dispatch(self, request: Request, call_next):
        # Process request with error handling
        try:
            response = await call_next(request)
            return response
        except LysError as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            mlex = _MiddlewareLysError(
                ex.status_code,
                ex.detail,
                ex.debug_message,
                os.path.split(exc_tb.tb_frame.f_code.co_filename)[1],
                exc_tb.tb_lineno,
                traceback.format_exc(),
                public_extensions=ex.extensions
            )
            raise mlex
        except Exception:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            mlex = _MiddlewareLysError(
                500,
                "INTERNAL_ERROR",
                exc_obj.__str__(),
                os.path.split(exc_tb.tb_frame.f_code.co_filename)[1],
                exc_tb.tb_lineno,
                traceback.format_exc(),
            )

            context = await self._get_context_from_request(request)
            await mlex.save_error_in_database(context)
            raise mlex

    @staticmethod
    def _get_from_request_state(request, name):
        return getattr(request.state, name, None)

    async def _get_context_from_request(self, request) -> Union[Dict[str, Any], None]:
        context: Dict[str, Any] = {}

        for key in self.saved_context_keys:
            value = self._get_from_request_state(request, key)
            if value is not None:
                context[key] = value

        if len(context.keys()) == 0:
            return None

        return context