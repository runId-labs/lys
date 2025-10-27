from abc import ABC, abstractmethod
from typing import Type, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util import classproperty

from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.services import EntityServiceInterface


class EntityFixtureInterface(ABC):
    """
    Manage the loading of entity fixtures to database
    """

    @classproperty
    @abstractmethod
    def service(self) -> Type[EntityServiceInterface]:
        raise NotImplementedError


    ####################################################################################################################
    #                                                    PROTECTED
    ####################################################################################################################

    @classmethod
    @abstractmethod
    async def _format_attributes(cls, attributes: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def _check_is_allowed_env(cls) -> bool:
        """
        Check if the fixtures can be loaded depending on the environment
        :return:
        """
        raise NotImplementedError

    ####################################################################################################################
    #                                                    PUBLIC
    ####################################################################################################################

    @classmethod
    @abstractmethod
    def is_viable(cls, obj: Any) -> bool:
        """
        Check if an object contains entity fixtures
        :param obj:
        :return:
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def _do_before_add(cls, obj: EntityInterface):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    async def load(cls):
        """
        Load fixtures to database
        :return:
        """
        raise NotImplementedError