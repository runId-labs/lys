from typing import Dict, Any, Union, TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.fastapi import BaseContext
from strawberry.types import Info as StrawberryInfo
from strawberry.types.info import RootValueType

from lys.core.interfaces.services import ServiceInterface, EntityServiceInterface


class Context(BaseContext):
    def __init__(self):
        super().__init__()

        self.service_class: type[ServiceInterface | EntityServiceInterface] | None = None
        self.session: AsyncSession | None = None

    def get_from_request_state(self, name, default_value=None):
        if self.request is not None:
            return getattr(self.request.state, name, default_value)

        return default_value

    def set_to_request_state(self, name, value):
        setattr(self.request.state, name, value)

    @property
    def access_type(self) -> Union[Dict[str, Any], bool]:
        return self.get_from_request_state("access_type", False)

    @access_type.setter
    def access_type(self, value: Union[Dict[str, Any], bool]):
        self.set_to_request_state("access_type", value)

    @property
    def connected_user(self) -> Union[Dict[str, Any], None]:
        return self.get_from_request_state("connected_user", None)

    @connected_user.setter
    def connected_user(self, value: Union[Dict[str, Any], None]):
        self.set_to_request_state("connected_user", value)

    @property
    def webservice_name(self):
        return self.get_from_request_state("webservice_name", None)

    @webservice_name.setter
    def webservice_name(self, value: Union[str, None]):
        self.set_to_request_state("webservice_name", value)

    @property
    def webservice_parameters(self) -> Dict[str, Any]:
        return self.get_from_request_state("webservice_parameters", {})

    @webservice_parameters.setter
    def webservice_parameters(self, value: Dict[str, Any]):
        self.set_to_request_state("webservice_parameters", value)


Info : TypeAlias = StrawberryInfo[Context, RootValueType]


def get_context() -> Context:
    return Context()
