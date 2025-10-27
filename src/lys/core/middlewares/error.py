import os
import sys
import traceback
from typing import List, Union, Dict, Any

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from lys.core.consts.environments import EnvironmentEnum
from lys.core.consts.tablenames import LOG_TABLENAME
from lys.core.errors import LysError
from lys.core.interfaces.middlewares import MiddlewareInterface
from lys.core.interfaces.services import EntityServiceInterface
from lys.core.utils.manager import AppManagerCallerMixin


class _MiddlewareLysError(AppManagerCallerMixin, HTTPException):
    def __init__(
            self,
            code: int,
            message: str,
            debug_message: str,
            file_name: str,
            line: int,
            traceback_,
    ) -> None:
        self.debug_message = debug_message
        self.file_name = file_name
        self.line = line
        self.traceback = traceback_

        if self.app_manager.settings.env == EnvironmentEnum.DEV:
            self.extensions = dict(
                debug_message= self.debug_message,
                file_name=self.file_name,
                line=self.line,
                traceback=self.traceback
            )

        HTTPException.__init__(
            self,
            status_code=code,
            detail=message
        )

    async def save_error_in_database(self, context: Union[Dict[str, Any], None] = None) -> None:
        log_service: EntityServiceInterface | None = self.app_manager.register.services.get(LOG_TABLENAME)

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
                traceback.format_exc()
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


