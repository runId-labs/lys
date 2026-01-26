from typing import Callable, Any, TypeVar, Generic, List, cast, Optional, Dict, Type, Union, Self

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.util import classproperty

from lys.core.entities import Entity
from lys.core.interfaces.services import ServiceInterface, EntityServiceInterface
from lys.core.managers.database import Base
from lys.core.utils.manager import AppManagerCallerMixin
from lys.core.utils.generic import resolve_service_name_from_generic

T = TypeVar('T', bound=Entity)


class Service(AppManagerCallerMixin, ServiceInterface):
    @classmethod
    async def on_initialize(cls):
        """
        Called when the application starts, after all components are registered.

        Override this method to perform initialization tasks like establishing
        connections, loading configuration, etc.

        This is called by AppRegistry.finalize_services() during app startup.
        """
        pass

    @classmethod
    async def on_shutdown(cls):
        """
        Called when the application shuts down.

        Override this method to perform cleanup tasks like closing connections,
        releasing resources, etc.

        This is called by AppRegistry.shutdown_services() during app shutdown.
        """
        pass

    @classmethod
    async def execute_parallel(cls, *query_functions: Callable[[AsyncSession], Any]):
        """
        Execute multiple queries in parallel using separate database sessions.

        This method is particularly useful for operations that can be run independently
        and where parallel execution can improve performance.

        Args:
            *query_functions: Variable number of callable functions that take an AsyncSession
                             as parameters and return query results.

        Returns:
            List of results from all query functions in the order they were provided.

        Example:
            results = await user_service.execute_parallel(
                lambda s: s.execute(select(User).where(User.company == "ACME")),
                lambda s: s.execute(select(User).where(User.is_super_user == True)),
                lambda s: s.execute(select(Client).where(Client.name.like("A%")))
            )

        Raises:
            RuntimeError: If the database manager is not available.
        """

        return await cls.app_manager.database.execute_parallel(*query_functions)


class EntityService(Generic[T], EntityServiceInterface, Service):
    """
    Generic service class for entity-based operations.

    This class provides a full CRUD (Create, Read, Update, Delete) interface for database
    entities. It uses Python generics to maintain type safety while providing reusable
    functionality across different entity types.

    The service automatically detects the entity type from the generic parameter and
    registers itself using the entity's __tablename__ attribute.

    Type Parameters:
        T: The entity type that extends BaseEntity

    Example:
        class UserService(EntityService[User]):
            pass  # service_name automatically set to User.__tablename__
    """

    def __init_subclass__(cls, **kwargs):
        """Automatically set service_name when subclass is created.

        This method is called when a new subclass of EntityService is defined.
        It automatically extracts the entity type from the generic parameter and
        sets the service_name to the entity's __tablename__ attribute.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__
        """
        super().__init_subclass__(**kwargs)
        # Use centralized generic type resolver to extract service_name
        service_name = resolve_service_name_from_generic(cls)
        if service_name:
            cls.service_name = service_name

    @classproperty
    def entity_class(self) -> Union[type[T], Base]:
        """Get the entity class managed by this service.

        Retrieves the entity class from the application registry using the service name.
        This allows for flexible entity registration and override capabilities.

        Returns:
            The entity class type associated with this service.
        """
        return self.app_manager.get_entity(self.service_name)

    @classmethod
    async def get_by_id(cls, entity_id: str, session:AsyncSession) -> Optional[T]:
        result = await session.execute(
            select(cls.entity_class).where(cls.entity_class.id == entity_id)
        )
        return result.scalar_one_or_none()

    @classmethod
    async def get_all(cls, session: AsyncSession, limit: int = 100, offset: int = 0) -> List[T]:
        result = await session.execute(
            select(cls.entity_class).limit(limit).offset(offset)
        )

        return cast(List[T], result.scalars().all())

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs) -> T:
        entity = cls.entity_class(**kwargs)
        session.add(entity)
        # Flush to get the generated ID
        await session.flush()
        return entity

    @classmethod
    async def update(cls, entity_id: str, session: AsyncSession, **kwargs) -> Optional[T]:
        await session.execute(
            update(cls.entity_class)
            .where(cls.entity_class.id == entity_id)
            .values(**kwargs)
        )
        return await cls.get_by_id(entity_id, session)

    @classmethod
    async def delete(cls, entity_id: str, session: AsyncSession) -> bool:
        result = await session.execute(
            delete(cls.entity_class).where(cls.entity_class.id == entity_id)
        )
        return bool(result.rowcount)

    @classmethod
    async def get_multiple_by_ids(cls, entity_ids: List[str], session: AsyncSession) -> List[T]:
        if not entity_ids:
            return []

        # For small lists, a single query is more efficient
        if len(entity_ids) <= 10:
            result = await session.execute(
                select(cls.entity_class).where(cls.entity_class.id.in_(entity_ids))
            )
            return cast(List[T], result.scalars().all())

        # For larger lists, parallelize using chunks
        chunk_size = 10
        chunks = [entity_ids[i:i + chunk_size] for i in range(0, len(entity_ids), chunk_size)]

        async def get_chunk(session_: AsyncSession, chunk_ids: List[str]):
            res = await session_.execute(
                select(cls.entity_class).where(cls.entity_class.id.in_(chunk_ids))
            )
            return res.scalars().all()

        query_functions = [
            lambda s: get_chunk(s, chunk) for chunk in chunks
        ]

        results = await cls.execute_parallel(*query_functions)

        # Flatten the results from all chunks
        entities = []
        for result in results:
            entities.extend(result)

        return entities

    @classmethod
    async def check_and_update(cls, entity: T, **formatted_attributes: Dict[str, Any]) -> tuple[T, bool]:
        """
        Check if data is really updated and update the entity instance if changes are detected.

        Args:
            entity: The entity instance to update
            **formatted_attributes: New attribute values to compare and apply

        Returns:
            Tuple of (updated_entity, is_updated_flag)
        """
        is_updated = False

        for key, new_attribute in formatted_attributes.items():
            if hasattr(entity, key):
                old_attribute = getattr(entity, key)

                if cls._values_differ(old_attribute, new_attribute):
                    setattr(entity, key, new_attribute)
                    is_updated = True

        return entity, is_updated

    @classmethod
    def _values_differ(cls, old_value: Any, new_value: Any) -> bool:
        """
        Compare two values to determine if they differ, handling lists and entities.

        Args:
            old_value: Current value
            new_value: New value to compare

        Returns:
            True if values differ, False otherwise
        """
        if isinstance(new_value, list):
            return cls._list_values_differ(old_value, new_value)
        elif isinstance(new_value, Entity):
            return old_value is None or old_value.id != new_value.id
        else:
            return old_value != new_value

    @staticmethod
    def _list_values_differ(old_list: List[Any], new_list: List[Any]) -> bool:
        """
        Compare two lists, handling both entity and primitive types.

        Args:
            old_list: Current list value
            new_list: New list value to compare

        Returns:
            True if lists differ, False otherwise
        """
        if not isinstance(old_list, list):
            return True

        if len(old_list) != len(new_list):
            return True

        # For entity lists, compare by ID
        if new_list and isinstance(new_list[0], Entity):
            old_ids = {item.id for item in old_list if isinstance(item, Entity)}
            new_ids = {item.id for item in new_list if isinstance(item, Entity)}
            return old_ids != new_ids

        # For primitive lists, compare directly
        return set(old_list) != set(new_list)
