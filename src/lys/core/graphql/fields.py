import dataclasses
import inspect
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type

import strawberry
from strawberry.extensions import FieldExtension

from lys.core.contexts import Info
from lys.core.graphql.interfaces import NodeInterface
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.permissions import generate_webservice_permission
from lys.core.registers import AppRegister, register_webservice
from lys.core.utils.webservice import WebserviceIsPublicType, format_filed_description


def _create_strawberry_field_config(
    resolver: Callable,
    name: Optional[str],
    is_subscription: bool,
    description: Optional[str],
    is_public: WebserviceIsPublicType,
    access_levels: List[str],
    is_licenced: bool,
    deprecation_reason: Optional[str],
    default: Any,
    default_factory: Union[Callable[..., object], object],
    metadata: Optional[Mapping[Any, Any]],
    directives: Optional[Sequence[object]],
    extensions: Optional[List[FieldExtension]],
    graphql_type: Optional[Any],
    init: Literal[True, False, None]
) -> dict:
    return {
        'resolver': resolver,
        'name': name,
        'is_subscription': is_subscription,
        'description': format_filed_description(description, is_public, access_levels, is_licenced),
        'permission_classes': [generate_webservice_permission(resolver.__name__)],
        'deprecation_reason': deprecation_reason,
        'default': default,
        'default_factory': default_factory,
        'metadata': metadata,
        'directives': directives,
        'extensions': extensions,
        'graphql_type': graphql_type,
        'init': init,
    }


def _apply_webservice_config(field, is_public: WebserviceIsPublicType, enabled: bool,
                                  access_levels: List[str], is_licenced: bool,
                                  allow_override: bool, register: AppRegister=None):
    return register_webservice(
        is_public=is_public,
        enabled=enabled,
        access_levels=access_levels,
        is_licenced=is_licenced,
        allow_override=allow_override,
        register=register,
    )(field)


def lys_typed_field(
        *,
        ensure_type: Type[NodeInterface],
        resolver_wrapper: Callable,
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
        register: AppRegister=None
) -> Any:

    def wrapper(resolver: Callable):
        wrapped_resolver = resolver_wrapper(resolver, ensure_type)

        field_config = _create_strawberry_field_config(
            resolver=wrapped_resolver,
            name=name,
            is_subscription=is_subscription,
            description=description,
            is_public=is_public,
            access_levels=access_levels,
            is_licenced=is_licenced,
            deprecation_reason=deprecation_reason,
            default=default,
            default_factory=default_factory,
            metadata=metadata,
            directives=directives,
            extensions=extensions,
            graphql_type=graphql_type,
            init=init,
        )

        field = strawberry.field(**field_config)
        field.base_resolver.type_annotation = ensure_type
        return _apply_webservice_config(field, is_public, enabled, access_levels, is_licenced, allow_override, register)

    return wrapper


def lys_field(
        ensure_type: Type[ServiceNode],
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
        register: AppRegister=None,
        has_session=True
) -> Any:
    def _resolver_generator(resolver: Callable, ensure_type_: Type[EntityNode]):
        async def inner_resolver(self, *args, info: Info, **kwargs) -> EntityNode:
            info.context.service_class = ensure_type_.service_class

            async def resolve_node():
                node = await resolver(self, *args, info=info, **kwargs)

                # check if the object is the same type of ensure type
                if not isinstance(node, ensure_type_):
                    raise ValueError(
                        "Wrong node type '%s'. (Expected: '%s')" % (
                            node.__class__.__name__,
                            ensure_type_.__name__
                        )
                    )

                return node

            async def wrapped() -> EntityNode:
                if has_session:
                    async with ensure_type_.app_manager.database.get_session() as session:
                        info.context.session = session

                        return await resolve_node()
                else:
                    return await resolve_node()

            return await wrapped()

        inner_resolver.__name__ = resolver.__name__
        inner_resolver.__module__ = resolver.__module__
        inner_resolver.__signature__ = inspect.signature(resolver)

        return inner_resolver

    return lys_typed_field(
        ensure_type=ensure_type,
        resolver_wrapper=_resolver_generator,
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
        register=register
    )


def lys_connection_field(
        *,
        ensure_type: Type[NodeInterface],
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
    def wrapper(resolver: Callable):
        sig = inspect.signature(resolver)
        parameter_value_list = list(sig.parameters.values())

        # check if order by schema type exist for the specified node
        order_by_type = getattr(ensure_type, "order_by_type", None)

        # if not the case create it and save it to make it reusable
        if order_by_type is None and len(ensure_type.order_by_attribute_map.keys()) > 0:
            class_str = """class %s :\n""" % (ensure_type.__name__ + "OderByType")

            for key in ensure_type.order_by_attribute_map.keys():
                class_str += """   %s : bool | None = strawberry.UNSET\n""" % key

            class_str += """order_by_type = %s""" % (ensure_type.__name__ + "OderByType")

            exec(class_str)

            loc = {}
            exec(class_str, globals(), loc)
            order_by_type = loc['order_by_type']
            ensure_type.order_by_type = order_by_type

        # add it to the webservice parameters
        if order_by_type is not None:
            parameter_value_list.append(
                inspect.Parameter(
                    "order_by",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=strawberry.input(
                        order_by_type,
                        one_of=True
                    ) | None,
                    default=None
                )
            )

        parameter_value_list.append(
            inspect.Parameter(
                "limit",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=int | None,
                default=None
            )
        )

        # overwrite webservice to compute order by if needed
        async def inner_resolver(*args, info: Info, **kwargs):
            info.context.service_class = ensure_type.service_class

            order_by = None
            if "order_by" in kwargs.keys():
                order_by = kwargs["order_by"]
                del kwargs["order_by"]

            limit = None

            if "limit" in kwargs.keys():
                limit = kwargs["limit"]
                del kwargs["limit"]

            stmt = await resolver(*args, info, **kwargs)

            if order_by is not None:
                for key in ensure_type.order_by_attribute_map.keys():
                    value = getattr(order_by, key, None)
                    if isinstance(value, bool):
                        column = ensure_type.order_by_attribute_map[key]
                        if value is True:
                            order_by_condition = column.asc()
                        else:
                            order_by_condition = column.desc()
                        stmt = stmt.order_by(None)
                        stmt = stmt.order_by(order_by_condition)
                        break

            if limit is not None:
                stmt = stmt.limit(limit)

            return stmt

        inner_resolver.__signature__ = sig.replace(
            parameters=tuple(parameter_value_list)
        )

        inner_resolver.__name__ = resolver.__name__
        inner_resolver.__module__ = resolver.__module__

        field_config = _create_strawberry_field_config(
            resolver=inner_resolver,
            name=name,
            is_subscription=is_subscription,
            description=description,
            is_public=is_public,
            access_levels=access_levels,
            is_licenced=is_licenced,
            deprecation_reason=deprecation_reason,
            default=default,
            default_factory=default_factory,
            metadata=metadata,
            directives=directives,
            extensions=extensions,
            graphql_type=graphql_type,
            init=init,
        )

        field = strawberry.field(**field_config)
        return _apply_webservice_config(field, is_public, enabled, access_levels, is_licenced, allow_override)

    return wrapper
