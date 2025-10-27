from typing import Any

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from lys.apps.base.consts import CORS_PLUGIN_KEY, CORS_PLUGIN_ALLOW_ORIGINS_KEY, CORS_PLUGIN_ALLOW_METHODS_KEY, \
    CORS_PLUGIN_ALLOW_HEADERS_KEY, CORS_PLUGIN_ALLOW_CREDENTIALS_KEY
from lys.core.interfaces.middlewares import MiddlewareInterface
from lys.core.utils.manager import AppManagerCallerMixin


class LysCorsMiddleware(MiddlewareInterface, AppManagerCallerMixin, CORSMiddleware):
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
