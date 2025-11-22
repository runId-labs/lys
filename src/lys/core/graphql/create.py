import dataclasses
import inspect
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type

from strawberry.extensions import FieldExtension

from lys.core.contexts import Info
from lys.core.entities import Entity
from lys.core.graphql.fields import lys_typed_field
from lys.core.graphql.nodes import EntityNode
from lys.core.utils.access import check_access_to_object
from lys.core.utils.webservice import WebserviceIsPublicType


def _creation_resolver_generator(resolver: Callable, ensure_type: Type[EntityNode]):

    async def inner_resolver(self, *args, info: Info, **kwargs) -> EntityNode:
        info.context.app_manager = ensure_type.app_manager

        # Use session from context (set by DatabaseSessionExtension)
        # The session is kept open by the extension for the entire GraphQL operation
        session = info.context.session

        entity_obj: Entity = await resolver(self, *args, info=info, **kwargs)

        # check if the object is the same type of ensure type entity
        if not isinstance(entity_obj, ensure_type.entity_class):
            raise ValueError(
                "Wrong entity type '%s'. (Expected: '%s')" % (
                    entity_obj.__class__.__name__,
                    ensure_type.entity_class.__name__
                )
            )

        # check permission again after updating
        await check_access_to_object(entity_obj, info.context)

        # add object to database
        session.add(entity_obj)

        # Flush changes to database before refresh
        await session.flush()

        # Refresh to load all relationships before creating the node
        await session.refresh(entity_obj)

        # return node
        return ensure_type.from_obj(entity_obj)

    inner_resolver.__name__ = resolver.__name__
    inner_resolver.__module__ = resolver.__module__
    inner_resolver.__signature__ = inspect.signature(resolver)

    return inner_resolver


def lys_creation(
    ensure_type: Type[EntityNode],
    is_public: WebserviceIsPublicType = False,
    enabled: bool = True,
    access_levels: List[str] = None,
    is_licenced: bool = True,
    allow_override: bool = False,
    name: Optional[str] = None,
    is_subscription: bool = False,
    description: Optional[str] = None,
    deprecation_reason: Optional[str] = None,
    default: Any = dataclasses.MISSING,
    default_factory: Union[Callable[..., object], object] = dataclasses.MISSING,
    metadata: Optional[Mapping[Any, Any]] = None,
    directives: Optional[Sequence[object]] = (),
    extensions: Optional[List[FieldExtension]] = None,
    graphql_type: Optional[Any] = None,
    init: Literal[True, False, None] = None,
    options: dict = None,
) -> Any:
    """
    Field used to update a specified database object
    :param ensure_type:
    :param is_public:
    :param enabled:
    :param access_levels:
    :param is_licenced:
    :param name:
    :param is_subscription:
    :param description:
    :param deprecation_reason:
    :param default:
    :param default_factory:
    :param metadata:
    :param directives:
    :param extensions:
    :param graphql_type:
    :param init:
    :return:
    """

    return lys_typed_field(
        ensure_type=ensure_type,
        resolver_wrapper=_creation_resolver_generator,
        is_public=is_public,
        enabled=enabled,
        access_levels=access_levels,
        is_licenced=is_licenced,
        allow_override=allow_override,
        name=name,
        is_subscription=is_subscription,
        description=description,
        deprecation_reason=deprecation_reason,
        default=default,
        default_factory=default_factory,
        metadata=metadata,
        directives=directives,
        extensions=extensions,
        graphql_type=graphql_type,
        init=init,
        options=options,
    )
