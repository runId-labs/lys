"""
Core middlewares for the lys framework.

This module provides:
- SecurityHeadersMiddleware: Adds standard HTTP security headers
- LysCorsMiddleware: CORS middleware with plugin configuration
- ErrorManagerMiddleware: Error handling and logging middleware
"""
import os
import sys
import traceback
from typing import List, Union, Dict, Any

from fastapi import FastAPI, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from lys.apps.base.consts import (
    CORS_PLUGIN_KEY,
    CORS_PLUGIN_ALLOW_ORIGINS_KEY,
    CORS_PLUGIN_ALLOW_METHODS_KEY,
    CORS_PLUGIN_ALLOW_HEADERS_KEY,
    CORS_PLUGIN_ALLOW_CREDENTIALS_KEY,
)
from lys.core.consts.environments import EnvironmentEnum
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