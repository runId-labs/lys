from abc import abstractmethod
from datetime import datetime
from typing import Type, Optional, Any, Self, Dict, List, TypeVar, Generic

import strawberry
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
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


class ServiceNodeMixin(AppManagerCallerMixin, NodeInterface):
    service_name: str

    @classmethod
    def get_node_by_name(cls, name: str) -> type[Self]:
        return cls.app_manager.register.get_node(name)

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
    @abstractmethod
    def from_obj(cls, entity: EntityInterface) -> 'EntityNode':
        raise NotImplementedError

    @classmethod
    async def resolve_node(cls, node_id: str, *,
                           info: Optional[Info] = None, required: bool = False):

        if cls.service_class is None:
            raise ValueError("%s.resolve_node() cannot be be called because %s.service_class return None" % (
                cls.__name__,
                cls.__name__
            ))

        node = None
        async with cls.app_manager.database.get_session() as session:
            info.context.session = session

            entity_obj: Optional[EntityInterface] = await get_db_object_and_check_access(
                node_id,
                cls.service_class,
                info.context,
                session,
                nullable=True
            )

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
        connection_extension = node_cls.__built_connection.get(node_cls.__name__)
        if connection_extension:
            return connection_extension

        class LysListConnection(AbstractListConnection, relay.ListConnection[node_cls]):

            page_info: LysPageInfo = field(
                description="Pagination data for this connection",
            )

            @classmethod
            def resolve_node(cls, node: Any, *, info: Info, **kwargs: Any) -> NodeInterface:
                service = node_cls.service_class()
                # check if entity type is correct
                if not isinstance(node, service.entity_class):
                    raise ValueError(
                        "Wrong entity type '%s'. (Expected: '%s')" % (node.__class__.__name__, node_cls.__name__)
                    )
                return node_cls.from_obj(node)

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

                    def count_entities(session: AsyncSession):
                        return get_select_total_count(protected_stmt, node_cls.service_class.entity_class, session)

                    [edges, total_count] = await node_cls.service_class.execute_parallel(
                        list_edges,
                        count_entities
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
            created_at: datetime
            updated_at: Optional[datetime]

            def __init__(self, id: str, code: str, enabled: bool, created_at: datetime, updated_at: Optional[datetime]):
                self.id = id
                self.code = code
                self.enabled = enabled
                self.created_at = created_at
                self.updated_at = updated_at

            @classmethod
            def from_obj(cls, entity: ParametricEntity):
                entity_class = cls.service_class.entity_class
                if not isinstance(entity, entity_class):
                    raise ValueError("Entity type error: %s != %s" % (entity.__class__, entity_class.__name__))

                return cls(
                    id=entity.id,
                    code=entity.code,
                    enabled=entity.enabled,
                    created_at=entity.created_at,
                    updated_at=entity.updated_at
                )

            @classproperty
            def order_by_attribute_map(self) -> Dict[str, Any]:
                entity_class = self.service_class.entity_class
                return {
                    "code": entity_class.id,
                    "created_at": entity_class.created_at
                }

        ParametricEntityNode.__name__ = class_.__name__
        return strawberry.type(ParametricEntityNode)

    return wrapper


@strawberry.type
class SuccessNode(NodeInterface):
    succeed: bool
    message: Optional[str] = None
