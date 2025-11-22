import dataclasses
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type

from strawberry import relay
from strawberry.extensions import FieldExtension

from lys.core.contexts import Info
from lys.core.graphql.fields import lys_typed_field
from lys.core.graphql.nodes import EntityNode
from lys.core.registers import AppRegister
from lys.core.utils.webservice import WebserviceIsPublicType


def _getter_resolver_generator(resolver: Callable, ensure_type: Type[EntityNode]):
    async def inner_resolver(id: relay.GlobalID, info: Info) -> EntityNode:
        info.context.app_manager = ensure_type.app_manager

        return await id.resolve_node(info, ensure_type=ensure_type)

    inner_resolver.__name__ = resolver.__name__
    inner_resolver.__module__ = resolver.__module__

    return inner_resolver


def lys_getter(
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
        register: AppRegister = None,
        options: dict = None
) -> Any:
    """
    Field used to get a specified database object
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
    :param register:
    :return:
    """

    return lys_typed_field(
        ensure_type=ensure_type,
        resolver_wrapper=_getter_resolver_generator,
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
        register=register,
        options=options,
    )
