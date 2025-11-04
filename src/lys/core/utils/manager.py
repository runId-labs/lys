from sqlalchemy.util import classproperty

from lys.core.managers.app import AppManager, LysAppManager


class AppManagerCallerMixin:
    _app_manager: AppManager = None

    @classproperty
    def app_manager(self) -> AppManager:
        if self._app_manager is None:
            self._app_manager = LysAppManager()
        return self._app_manager

    @classmethod
    def configure_app_manager_for_testing(cls, app_manager: AppManager):
        cls._app_manager = app_manager