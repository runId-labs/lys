from abc import ABC, abstractmethod
from typing import Dict, Any, Type

from sqlalchemy.util import classproperty

from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.services import EntityServiceInterface


class NodeInterface:
    @classproperty
    @abstractmethod
    def service_class(self) -> Type[EntityServiceInterface]:
        raise NotImplementedError


class EntityNodeInterface(NodeInterface):
    @classproperty
    @abstractmethod
    def entity_class(self) -> Type[EntityInterface]:
        raise NotImplementedError

    @classproperty
    @abstractmethod
    def order_by_attribute_map(self) -> Dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_obj(cls, obj):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def build_list_connection(node_cls):
        raise NotImplementedError


class QueryInterface:
    pass


class MutationInterface:
    pass


class SubscriptionInterface:
    pass