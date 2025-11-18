import dataclasses
import inspect
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type

from strawberry import relay
from strawberry.extensions import FieldExtension

from lys.core.consts.errors import NOT_FOUND_ERROR
from lys.core.contexts import Info
from lys.core.entities import Entity
from lys.core.errors import LysError
from lys.core.graphql.fields import lys_typed_field
from lys.core.graphql.nodes import EntityNode
from lys.core.utils.access import get_db_object_and_check_access, check_access_to_object
from lys.core.utils.webservice import WebserviceIsPublicType


def _edition_resolver_generator(resolver: Callable, ensure_type: Type[EntityNode]):
    sig = inspect.signature(resolver)
    parameter_value_list = list(sig.parameters.values())

    last_parameter_index = len(parameter_value_list)

    parameters = [
        parameter_value_list[0],
        inspect.Parameter("id", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=relay.GlobalID),
        *parameter_value_list[2:last_parameter_index]
    ]

    async def inner_resolver(self, id: relay.GlobalID, *args, info: Info, **kwargs) -> EntityNode:
        info.context.app_manager = ensure_type.app_manager

        async def wrapped() -> EntityNode:
            async with ensure_type.app_manager.database.get_session() as session:
                info.context.session = session

                # get object and check access on it
                obj: Optional[Entity] = await get_db_object_and_check_access(
                    id.node_id,
                    ensure_type.service_class,
                    info.context,
                    session=session
                )

                if not obj:
                    raise LysError(
                        NOT_FOUND_ERROR,
                        "_edition_resolver_generator: Unknown entity with type '%s' and id '%s'" % (
                            ensure_type.service_class.entity_class,
                            id.node_id
                        )
                    )

                # update the retrieved object with the resolver
                await resolver(self, obj=obj, *args, info=info, **kwargs)

                # check permission again after updating
                await check_access_to_object(obj, info.context)

                # Flush changes to database before refresh
                await session.flush()

                # Refresh to load all relationships before creating the node
                await session.refresh(obj)

                return ensure_type.from_obj(obj)

        return await wrapped()

    inner_resolver.__signature__ = sig.replace(
        parameters=tuple(parameters)
    )

    inner_resolver.__name__ = resolver.__name__
    inner_resolver.__module__ = resolver.__module__

    return inner_resolver


def lys_edition(
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
        resolver_wrapper=_edition_resolver_generator,
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
    )

