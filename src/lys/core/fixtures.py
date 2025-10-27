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
from lys.core.utils.database import check_is_needing_session
from lys.core.utils.manager import AppManagerCallerMixin

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
        # Automatically define service_name when creating subclasses
        for base in cls.__orig_bases__:
            if hasattr(base, '__args__'):
                service_class = base.__args__[0]
                cls.service_name = service_class.service_name
                break

    @classproperty
    def service(self) -> Type[ServiceInterface]:
        return self.get_service_by_name(self.service_name)

    ####################################################################################################################
    #                                                    PROTECTED
    ####################################################################################################################

    @classmethod
    async def _format_attributes(cls, attributes: Dict[str, Any], session: AsyncSession) -> Dict[str, Any]:
        formatted_attributes: Dict[str, Any] = {}

        for key, attribute in attributes.items():
            method_name = "format_" + key
            if hasattr(cls, method_name) and callable(getattr(cls, method_name)):
                method = getattr(cls, method_name)
                if check_is_needing_session(method):
                    formatted_attributes[key] = await method(attribute, session=session)
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
        pass

    @classmethod
    async def _load_business_data(cls, session, entity_class: Type[Entity]):
        """
        Load business entity data (non-PROD only).

        Returns:
            Tuple of (deleted_count, added_count)
        """
        deleted_count = 0

        if cls.delete_previous_data:
            # Delete all existing rows
            stmt = delete(entity_class)
            result = await session.execute(stmt)
            deleted_count = result.rowcount

        # Prepare formatted attributes
        formatted_attributes_list = []
        for data in cls.data_list:
            formatted_attributes_list.append(
                await cls._format_attributes(data.get("attributes", {}), session=session)
            )

        # Insert all data from data_list
        for attributes in formatted_attributes_list:
            obj = entity_class(**attributes)
            await cls._do_before_add(obj)
            session.add(obj)

        added_count = len(cls.data_list)

        return deleted_count, added_count

    @classmethod
    async def _load_parametric_data(cls, session, entity_class: Type[ParametricEntity], service):
        """
        Load parametric entity data with update/disable logic.

        Returns:
            Tuple of (deleted_count, added_count, updated_count, unchanged_count)
        """
        deleted_count = 0
        added_count = 0
        updated_count = 0
        unchanged_count = 0

        # Disable entities not in data_list
        if cls.delete_previous_data:
            stmt = update(entity_class).where(
                entity_class.id.notin_([data["id"] for data in cls.data_list])
            ).values(enabled=False)
            result = await session.execute(stmt)
            deleted_count = result.rowcount

        # Process each data item
        for data in cls.data_list:
            stmt = select(entity_class).where(entity_class.id == data["id"]).limit(1)
            result = await session.execute(stmt)
            obj: Optional[Entity] = result.scalars().one_or_none()

            attributes: Dict[str, Any] = data.get("attributes", {})

            if obj is not None:
                # Update existing entity
                if len(attributes.keys()):
                    formatted_attributes = await cls._format_attributes(attributes, session=session)
                    obj_updated, is_updated = await service.check_and_update(
                        entity=obj, **formatted_attributes
                    )

                    if is_updated:
                        updated_count += 1
                    else:
                        unchanged_count += 1
                else:
                    unchanged_count += 1
            else:
                # Create new entity
                formatted_attributes = await cls._format_attributes(attributes, session=session)
                obj = entity_class(id=data["id"], **formatted_attributes)

                await cls._do_before_add(obj)
                session.add(obj)
                added_count += 1

        return deleted_count, added_count, updated_count, unchanged_count

    @classmethod
    async def _inner_load(cls, session, entity_class: Type[Entity], service: EntityServiceInterface):
        """
        Internal load method with session management.

        Args:
            session: Database session from context manager
            entity_class: Entity class to load fixtures for
            service: Service instance for entity operations
        """
        # Initialize log values
        deleted_count = 0
        added_count = 0
        updated_count = 0
        unchanged_count = 0

        _FixtureLogger.log_start(entity_class.__tablename__)

        if issubclass(entity_class, ParametricEntity):
            # Handle parametric entities (reference data)
            deleted_count, added_count, updated_count, unchanged_count = await cls._load_parametric_data(
                session, entity_class, service
            )

        elif not cls.app_manager.settings.env == EnvironmentEnum.PROD:
            # Handle business entities (only in non-PROD environments)
            deleted_count, added_count = await cls._load_business_data(
                session, entity_class
            )

        # Log results
        _FixtureLogger.log_results(entity_class.__tablename__, deleted_count, added_count, updated_count,
                                   unchanged_count)

    ####################################################################################################################
    #                                                    PUBLIC
    ####################################################################################################################

    @classmethod
    def get_service_by_name(cls, service_name: str) -> Type[ServiceInterface]:
        return cls.app_manager.register.get_service(service_name)

    @classmethod
    def get_entity_by_name(cls, tablename: str) -> Type[EntityInterface]:
        return cls.app_manager.register.get_entity(tablename)

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
