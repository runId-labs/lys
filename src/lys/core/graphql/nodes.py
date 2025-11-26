import asyncio
from abc import abstractmethod
from datetime import datetime
from typing import Type, Optional, Any, Self, Dict, List, TypeVar, Generic, overload, Union

import strawberry
from sqlalchemy import Select, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.util import classproperty
from strawberry import relay, field
from strawberry.relay import Edge
from strawberry.types import Info
from strawberry.utils.aio import aenumerate
from strawberry.utils.await_maybe import AwaitableOrValue

from lys.core.consts.errors import NOT_FOUND_ERROR
from lys.core.entities import ParametricEntity
from lys.core.errors import LysError
from lys.core.graphql.abstracts import AbstractListConnection
from lys.core.graphql.interfaces import NodeInterface, EntityNodeInterface
from lys.core.graphql.types import LysPageInfo
from lys.core.interfaces.entities import EntityInterface
from lys.core.interfaces.services import ServiceInterface
from lys.core.permissions import add_access_constraints
from lys.core.utils.access import get_db_object_and_check_access
from lys.core.utils.database import get_select_total_count
from lys.core.utils.manager import AppManagerCallerMixin
from lys.core.utils.generic import resolve_service_name_from_generic

T = TypeVar('T', bound=ServiceInterface)
TNode = TypeVar('TNode', bound='EntityNode')


class ServiceNodeMixin(AppManagerCallerMixin, NodeInterface):
    service_name: str

    @classmethod
    def get_node_by_name(cls, name: str) -> type[Self]:
        return cls.app_manager.registry.get_node(name)

    @classmethod
    def get_effective_node(cls) -> type[Self]:
        return cls.get_node_by_name(cls.__name__)

    @classproperty
    def service_class(self) -> Type[ServiceInterface]:
        return self.app_manager.get_service(self.service_name)


class ServiceNode(Generic[T], ServiceNodeMixin):

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Use centralized generic type resolver to extract service_name
        service_name = resolve_service_name_from_generic(cls)
        if service_name:
            cls.service_name = service_name


class EntityNode(Generic[T], ServiceNodeMixin):
    __built_connection: Dict[str, Type[relay.ListConnection]] = {}
    service_name: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Use centralized generic type resolver to extract service_name
        service_name = resolve_service_name_from_generic(cls)
        if service_name:
            cls.service_name = service_name

    @classproperty
    def entity_class(self) -> Type[EntityInterface]:
        return self.app_manager.get_entity(self.service_name)

    @classmethod
    def from_obj(cls, entity: EntityInterface) -> 'EntityNode':
        """
        Convert an entity to a node with automatic field mapping.

        This default implementation automatically maps entity attributes to node fields
        based on the node's type annotations. Fields starting with '_' are handled specially:
        - '_entity' is automatically set to store the source entity for lazy loading

        Subclasses can override this method for custom mapping logic.

        Args:
            entity: The entity instance to convert

        Returns:
            EntityNode instance with mapped fields
        """
        # Collect all non-private fields from annotations
        fields = {}
        for field_name in cls.__annotations__:
            # Skip private fields (will be handled separately)
            if field_name.startswith('_'):
                continue

            # Skip methods decorated with @strawberry.field (lazy-loaded relations)
            # These are computed properties that should not be passed to __init__
            if hasattr(cls, field_name):
                class_attr = getattr(cls, field_name)
                if callable(class_attr) or hasattr(class_attr, '__func__'):
                    continue

            # Map field if attribute exists on entity
            if hasattr(entity, field_name):
                fields[field_name] = getattr(entity, field_name)

        # Store entity if _entity field is defined
        if '_entity' in cls.__annotations__:
            fields['_entity'] = entity

        return cls(**fields)

    async def _lazy_load_relation(
        self,
        relation_name: str,
        node_class: Type[TNode],
        info: 'Info'
    ) -> Union[TNode, None]:
        """
        Async lazy load a single relation from the stored entity.

        This method uses the session from the GraphQL context to explicitly load
        the relationship using session.refresh(). This is required for SQLAlchemy async
        to properly load relationships.

        If the underlying foreign key is non-nullable and the relation is None, an error is raised
        to ensure GraphQL schema consistency with database constraints.

        Args:
            relation_name: Name of the relation attribute on the entity (e.g., 'user', 'client')
            node_class: Node class to convert the relation to (e.g., UserNode, ClientNode)
            info: GraphQL Info context containing the database session

        Returns:
            Node instance for the relation, or None if relation is nullable and None

        Raises:
            AttributeError: If the entity is not loaded
            ValueError: If the relation is non-nullable but None

        Example:
            @strawberry.field
            async def user(self, info: Info) -> UserNode:
                return await self._lazy_load_relation('user', UserNode, info)
        """
        if not hasattr(self, '_entity'):
            raise AttributeError(
                f"{self.__class__.__name__} must have '_entity' field to use lazy loading. "
                f"Add '_entity: strawberry.Private[YourEntity]' to the node definition."
            )

        # Use session from context to refresh the entity with the relationship
        session = info.context.session
        await session.refresh(self._entity, [relation_name])

        # Now we can safely access the relationship (it's loaded in memory)
        entity_relation = getattr(self._entity, relation_name, None)

        if entity_relation is None:
            is_nullable = self._is_relation_nullable(relation_name)
            if not is_nullable:
                raise ValueError(
                    f"Relation '{relation_name}' on {self._entity.__class__.__name__} is None, "
                    f"but the underlying foreign key is non-nullable. This indicates a data integrity issue."
                )
            return None

        return node_class.get_effective_node().from_obj(entity_relation)

    def _is_relation_nullable(self, relation_name: str) -> bool:
        """
        Check if a relation's foreign key columns are nullable.

        Args:
            relation_name: Name of the relation attribute on the entity

        Returns:
            True if at least one foreign key column is nullable, False if all are non-nullable
        """
        mapper = inspect(self._entity.__class__)

        if relation_name not in mapper.relationships:
            return True

        relationship = mapper.relationships[relation_name]

        for local_col in relationship.local_columns:
            if local_col.nullable:
                return True

        return False

    async def _lazy_load_relation_list(
        self,
        relation_name: str,
        node_class: Type[TNode],
        info: 'Info'
    ) -> List[TNode]:
        """
        Async lazy load a list of relations from the stored entity.

        This method uses the session from the GraphQL context to explicitly load
        the collection relationship using session.refresh(). This is required for
        SQLAlchemy async to properly load relationships.

        Args:
            relation_name: Name of the relation attribute on the entity (e.g., 'roles', 'permissions')
            node_class: Node class to convert each relation item to (e.g., RoleNode)
            info: GraphQL Info context containing the database session

        Returns:
            List of node instances for the relation items

        Raises:
            AttributeError: If the entity is not loaded

        Example:
            @strawberry.field
            async def roles(self, info: Info) -> List[RoleNode]:
                return await self._lazy_load_relation_list('roles', RoleNode, info)
        """
        if not hasattr(self, '_entity'):
            raise AttributeError(
                f"{self.__class__.__name__} must have '_entity' field to use lazy loading. "
                f"Add '_entity: strawberry.Private[YourEntity]' to the node definition."
            )

        # Use session from context to refresh the entity with the relationship collection
        session = info.context.session
        await session.refresh(self._entity, [relation_name])

        # Now we can safely access the relationship collection (it's loaded in memory)
        entity_relations = getattr(self._entity, relation_name, [])
        return [node_class.get_effective_node().from_obj(item) for item in entity_relations]

    @classmethod
    async def resolve_node(cls, node_id: str, *,
                           info: Optional[Info] = None, required: bool = False):

        if cls.service_class is None:
            raise ValueError("%s.resolve_node() cannot be be called because %s.service_class return None" % (
                cls.__name__,
                cls.__name__
            ))

        # Use session from context (set by DatabaseSessionExtension)
        # The session is kept open by the extension for the entire GraphQL operation
        session = info.context.session

        entity_obj: Optional[EntityInterface] = await get_db_object_and_check_access(
            node_id,
            cls.service_class,
            info.context,
            session,
            nullable=True
        )

        node = None
        if entity_obj:
            node = cls.from_obj(entity_obj)

        if required and node is None:
            raise LysError(
                NOT_FOUND_ERROR,
                "Entity with type '%s' and id '%s' was not found." % (cls.entity_class, node_id)
            )

        return node

    @classproperty
    def order_by_attribute_map(self) -> Dict[str, Any]:
        """
        Define allowed "order by" keys and them relation with the entity
        """
        entity_class = self.service_class.entity_class
        return {
            "created_at": entity_class.created_at
        }

    @classmethod
    def build_list_connection(node_cls):
        effective_node_cls: type[EntityNode[T]] = node_cls.get_effective_node()
        connection_extension = effective_node_cls.__built_connection.get(effective_node_cls.__name__)
        if connection_extension:
            return connection_extension

        class LysListConnection(AbstractListConnection, relay.ListConnection[effective_node_cls]):

            page_info: LysPageInfo = field(
                description="Pagination data for this connection",
            )

            @classmethod
            def resolve_node(cls, node: Any, *, info: Info, **kwargs: Any) -> NodeInterface:
                service = effective_node_cls.service_class()
                # check if entity type is correct
                if not isinstance(node, service.entity_class):
                    raise ValueError(
                        "Wrong entity type '%s'. (Expected: '%s')" % (node.__class__.__name__, effective_node_cls.__name__)
                    )
                return effective_node_cls.from_obj(node)

            @classmethod
            def resolve_connection(
                    cls,
                    stmt: Select,
                    *,
                    info: Info,
                    before: Optional[str] = None,
                    after: Optional[str] = None,
                    first: Optional[int] = None,
                    last: Optional[int] = None,
                    **kwargs: Any,
            ) -> AwaitableOrValue[Self]:
                slice_metadata, edge_class = cls.before_compute_returning_list(info, before, after, first, last)

                async def resolver():
                    # add right to query
                    protected_stmt = await add_access_constraints(stmt, info.context, node_cls.entity_class,
                                                                  node_cls.app_manager)

                    if slice_metadata.overfetch:
                        protected_stmt = protected_stmt.limit(slice_metadata.overfetch)

                    if slice_metadata.start:
                        protected_stmt = protected_stmt.offset(slice_metadata.start)

                    async def list_edges(session: AsyncSession) -> List[Edge]:
                        iterator = await session.stream_scalars(protected_stmt)
                        return [
                            edge_class.resolve_edge(
                                cls.resolve_node(v, info=info, **kwargs),
                                cursor=slice_metadata.start + i,
                            )
                            async for i, v in aenumerate(iterator)
                        ]

                    async def count_entities_with_own_session():
                        # Use a separate session for counting to allow parallel execution
                        # The main session is used for loading entities (they stay attached)
                        async with node_cls.app_manager.database.get_session() as count_session:
                            return await get_select_total_count(
                                protected_stmt,
                                node_cls.service_class.entity_class,
                                count_session
                            )

                    # Use session from context (set by DatabaseSessionExtension) for loading entities
                    # This keeps entities attached to the session for the entire GraphQL operation
                    session = info.context.session

                    # Execute list_edges and count_entities in parallel
                    # - list_edges uses the main session (entities stay attached)
                    # - count_entities uses its own session (no conflict)
                    [edges, total_count] = await asyncio.gather(
                        list_edges(session),
                        count_entities_with_own_session()
                    )

                    return cls.prepare_returning_list(slice_metadata, edges, last, total_count)

                return resolver()

        LysListConnection.__name__ = node_cls.__name__ + "ListConnection"

        connection_extension = strawberry.type(LysListConnection)

        node_cls.__built_connection[node_cls.__name__] = connection_extension

        return connection_extension


def parametric_node(service_class: Type[ServiceInterface]):
    """
    All Parametric Nodes have the same graphql properties
    This decorator is used to automatize their creations
    :param service_class: related service class
    :return:
    """

    def wrapper(class_):
        class ParametricEntityNode(EntityNode[service_class], relay.Node):
            id: relay.NodeID[str]
            code: str
            enabled: bool
            description: Optional[str]
            created_at: datetime
            updated_at: Optional[datetime]
            _entity: strawberry.Private[ParametricEntity]

            def __init__(self, entity: ParametricEntity):
                self.id = entity.id
                self.code = entity.code
                self.enabled = entity.enabled
                self.description = entity.description
                self.created_at = entity.created_at
                self.updated_at = entity.updated_at
                self._entity = entity

            @classmethod
            def from_obj(cls, entity: ParametricEntity):
                entity_class = cls.service_class.entity_class
                if not isinstance(entity, entity_class):
                    raise ValueError("Entity type error: %s != %s" % (entity.__class__, entity_class.__name__))

                return cls(entity)

            @classproperty
            def order_by_attribute_map(self) -> Dict[str, Any]:
                entity_class = self.service_class.entity_class
                return {
                    "code": entity_class.id,
                    "created_at": entity_class.created_at
                }

        ParametricEntityNode.__name__ = class_.__name__
        return ParametricEntityNode

    return wrapper


class SuccessNode(NodeInterface):
    succeed: bool
    message: Optional[str] = None
