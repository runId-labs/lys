import logging
from typing import Dict, Any, List, Type, Optional, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import delete, select, update
from sqlalchemy.util import classproperty

from lys.core.consts.environments import EnvironmentEnum
from lys.core.entities import ParametricEntity, Entity
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.fixtures import EntityFixtureInterface
from lys.core.interfaces.services import EntityServiceInterface, ServiceInterface
from lys.core.models.fixtures import EntityFixturesModel
from lys.core.services import EntityService
from lys.core.strategies.fixture_loading import FixtureLoadingStrategyFactory
from lys.core.utils.database import check_is_needing_session
from lys.core.utils.manager import AppManagerCallerMixin
from lys.core.utils.generic import resolve_service_name_from_generic

T = TypeVar('T', bound=EntityService)


class _FixtureValidator:
    """
    Helper class to encapsulate fixture validation logic
    """

    @staticmethod
    def is_valid_fixture_class(cls, obj: Any) -> bool:
        """Check if an object is a valid fixture class"""
        return (issubclass(obj, cls) and
                obj.__class__.__name__ != "EntityFixtures")

    @staticmethod
    def has_required_attributes(obj: Any) -> bool:
        """Check if fixture class has required attributes"""
        return (obj.model is not None and
                obj.data_list is not None)


class _FixtureLogger:
    """
    Helper class to centralize logging messages and formatting
    """
    LOG_MESSAGES = {
        "START": "\tSTART LOADING table '{table}'",
        "REPORT_HEADER": "\tREPORT table '{table}'",
        "DELETED": "\t  -> deleted/disabled object count {count}",
        "ADDED": "\t  -> added object count {count}",
        "UPDATED": "\t  -> updated object count {count}",
        "UNCHANGED": "\t  -> unchanged object count {count}",
        "SEPARATOR": ""
    }

    @classmethod
    def log_start(cls, table_name: str):
        """Log start of fixture loading"""
        logging.info(cls.LOG_MESSAGES["START"].format(table=table_name))

    @classmethod
    def log_results(cls, table_name: str, deleted_count: int, added_count: int,
                    updated_count: int, unchanged_count: int):
        """Log fixture loading results"""
        logging.info(cls.LOG_MESSAGES["SEPARATOR"])
        logging.info(cls.LOG_MESSAGES["REPORT_HEADER"].format(table=table_name))
        logging.info(cls.LOG_MESSAGES["DELETED"].format(count=deleted_count))
        logging.info(cls.LOG_MESSAGES["ADDED"].format(count=added_count))
        logging.info(cls.LOG_MESSAGES["UPDATED"].format(count=updated_count))
        logging.info(cls.LOG_MESSAGES["UNCHANGED"].format(count=unchanged_count))
        logging.info(cls.LOG_MESSAGES["SEPARATOR"])


class EntityFixtures(Generic[T], AppManagerCallerMixin, EntityFixtureInterface):
    """
    Manage the loading of entity fixtures to the database
    """
    service_name: str
    model: Type[EntityFixturesModel]
    _allowed_envs: List[EnvironmentEnum] = []
    data_list: List[Dict[str, Any]]
    """
    # determine if data already in database table must be deleted 
    """
    delete_previous_data: bool = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Use centralized generic type resolver to extract service_name
        service_name = resolve_service_name_from_generic(cls)
        if service_name:
            cls.service_name = service_name

    @classproperty
    def service(self) -> Type[ServiceInterface]:
        return self.app_manager.get_service(self.service_name)

    ####################################################################################################################
    #                                                    PROTECTED
    ####################################################################################################################

    @classmethod
    async def create_from_service(
        cls,
        attributes: Dict[str, Any],
        session: AsyncSession
    ) -> Entity | None:
        """
        Override to use a custom service method for entity creation.

        When defined in a subclass, this method is called instead of the standard
        entity instantiation for NEW entities only. If the entity already exists
        (upsert mode), the standard update logic is used.

        Args:
            attributes: Raw fixture attributes (before formatting)
            session: Database session

        Returns:
            Created entity, or None to use standard creation behavior
        """
        return None

    @classmethod
    async def _format_attributes(
        cls,
        attributes: Dict[str, Any],
        session: AsyncSession,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        formatted_attributes: Dict[str, Any] = {}

        for key, attribute in attributes.items():
            method_name = "format_" + key
            if hasattr(cls, method_name) and callable(getattr(cls, method_name)):
                method = getattr(cls, method_name)
                needs_session = check_is_needing_session(method)
                needs_extra_data = "extra_data" in method.__annotations__

                if needs_session and needs_extra_data:
                    formatted_attributes[key] = await method(attribute, session=session, extra_data=extra_data)
                elif needs_session:
                    formatted_attributes[key] = await method(attribute, session=session)
                elif needs_extra_data:
                    formatted_attributes[key] = await method(attribute, extra_data=extra_data)
                else:
                    formatted_attributes[key] = await method(attribute)
            else:
                formatted_attributes[key] = attribute

        return formatted_attributes

    @classmethod
    def _check_is_allowed_env(cls) -> bool:
        """
        Check if the fixtures can be loaded depending on the environment
        :return:
        """

        if issubclass(cls.service.entity_class, ParametricEntity):
            # if it is a parametric entity load it
            return True
        else:
            # else check for which environments the fixtures must be loaded
            return cls.app_manager.settings.env in cls._allowed_envs

    @classmethod
    async def _do_before_add(cls, obj: Entity):
        """
        Hook method called before adding an entity to the session.

        Subclasses can override this method to perform additional
        operations before an entity is added during fixture loading.

        Args:
            obj: The entity instance about to be added
        """
        pass

    @classmethod
    async def _inner_load(cls, session, entity_class: Type[Entity], service: EntityServiceInterface):
        """
        Internal load method with session management using strategy pattern.

        Args:
            session: Database session from context manager
            entity_class: Entity class to load fixtures for
            service: Service instance for entity operations
        """
        _FixtureLogger.log_start(entity_class.__tablename__)

        # Use strategy pattern to determine loading behavior
        strategy = FixtureLoadingStrategyFactory.create_strategy(entity_class)

        # Check if business data should be loaded based on environment
        if not issubclass(entity_class, ParametricEntity):
            if cls.app_manager.settings.env == EnvironmentEnum.PROD:
                # Skip business data loading in production
                _FixtureLogger.log_results(entity_class.__tablename__, 0, 0, 0, 0)
                return

        # Execute the loading strategy
        deleted_count, added_count, updated_count, unchanged_count = await strategy.load(
            cls, session, entity_class, service
        )

        # Log results
        _FixtureLogger.log_results(
            entity_class.__tablename__,
            deleted_count,
            added_count,
            updated_count,
            unchanged_count
        )

    ####################################################################################################################
    #                                                    PUBLIC
    ####################################################################################################################

    @classmethod
    def is_viable(cls, obj: 'EntityFixtures') -> bool:
        """
        Check if an object contains entity fixtures
        :param obj:
        :return:
        """
        return (_FixtureValidator.is_valid_fixture_class(cls, obj) and
                cls._check_is_allowed_env() and
                _FixtureValidator.has_required_attributes(obj))

    @classmethod
    async def load(cls):
        """
        Load fixtures to database with proper session management.

        Uses context manager for automatic commit/rollback and session cleanup.
        """
        # Get service and entity class once and reuse them
        entity_class = cls.service.entity_class

        # Validate data_list before loading
        if issubclass(entity_class, Entity):
            for data in cls.data_list:
                cls.model.validate(data)

        db_manager = cls.app_manager.database
        # Use the database manager's session context for proper transaction handling
        async with db_manager.get_session() as session:
            await cls._inner_load(session, entity_class, cls.service)
