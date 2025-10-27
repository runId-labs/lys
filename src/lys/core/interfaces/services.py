from abc import ABC, abstractmethod
from typing import Callable, Any, Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util import classproperty

from lys.core.interfaces.entities import EntityInterface


class ServiceInterface(ABC):
    @classmethod
    @abstractmethod
    async def execute_parallel(cls, *query_functions: Callable[[AsyncSession], Any]):
        raise NotImplementedError


class EntityServiceInterface(ServiceInterface):

    @classproperty
    @abstractmethod
    def entity_class(self) -> EntityInterface:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def get_by_id(cls, entity_id: str, session:AsyncSession) -> Optional[EntityInterface]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def get_all(cls, session: AsyncSession, limit: int = 100, offset: int = 0) -> List[EntityInterface]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def create(cls, session: AsyncSession, **kwargs) -> EntityInterface:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def update(cls, entity_id: str, session: AsyncSession, **kwargs) -> Optional[EntityInterface]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def delete(cls, entity_id: str, session: AsyncSession) -> bool:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def get_multiple_by_ids(cls, entity_ids: List[str], session: AsyncSession) -> List[EntityInterface]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def check_and_update(cls, entity: EntityInterface, **formatted_attributes: Dict[str, Any]) \
            -> tuple[EntityInterface, bool]:
        raise NotImplementedError