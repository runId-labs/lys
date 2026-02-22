import dataclasses
import inspect
import logging
from typing import Annotated, Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type, get_origin, get_args

import strawberry
from strawberry.extensions import FieldExtension
from strawberry.annotation import StrawberryAnnotation

from lys.core.contexts import Info
from lys.core.graphql.interfaces import NodeInterface
from lys.core.graphql.nodes import EntityNode, ServiceNode, ServiceNodeMixin
from lys.core.permissions import generate_webservice_permission
from lys.core.registries import AppRegistry, register_webservice
from lys.core.utils.webservice import WebserviceIsPublicType, format_filed_description

logger = logging.getLogger(__name__)


def create_strawberry_field_config(
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
                                  allow_override: bool, description: str = None,
                                  register: AppRegistry = None, options: dict = None):
    return register_webservice(
        is_public=is_public,
        enabled=enabled,
        access_levels=access_levels,
        is_licenced=is_licenced,
        allow_override=allow_override,
        description=description,
        register=register,
        options=options,
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
        register: AppRegistry = None,
        options: dict = None
) -> Any:
    effective_ensure_type = ensure_type.get_effective_node()

    def wrapper(resolver: Callable):
        wrapped_resolver = resolver_wrapper(resolver, effective_ensure_type)

        field_config = create_strawberry_field_config(
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

        # Preserve Optional type annotation from the original resolver
        original_return_type = inspect.signature(resolver).return_annotation
        if get_origin(original_return_type) is Union:
            # Check if it's Optional (Union with None)
            args = get_args(original_return_type)
            if type(None) in args:
                # It's Optional, preserve it
                field.base_resolver.type_annotation = StrawberryAnnotation(Optional[effective_ensure_type])
            else:
                field.base_resolver.type_annotation = StrawberryAnnotation(effective_ensure_type)
        else:
            field.base_resolver.type_annotation = StrawberryAnnotation(effective_ensure_type)

        return _apply_webservice_config(field, is_public, enabled, access_levels, is_licenced, allow_override, description, register, options)

    return wrapper


def lys_field(
        ensure_type: Type[ServiceNodeMixin],
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
        register: AppRegistry = None,
        has_session=True,
        options: dict = None
) -> Any:
    def _resolver_generator(resolver: Callable, ensure_type_: Type[ServiceNodeMixin]):
        async def inner_resolver(self, *args, info: Info, **kwargs) -> ServiceNodeMixin:
            info.context.app_manager = ensure_type_.app_manager

            # Audit log for lys_field accessing sensitive entities
            entity_class = (
                getattr(ensure_type_.service_class, "entity_class", None)
                if hasattr(ensure_type_, "service_name")
                else None
            )
            if entity_class is not None and getattr(entity_class, "_sensitive", False):
                connected_user = info.context.connected_user
                logger.info(
                    "AUDIT: Field access to %s by user=%s via webservice=%s",
                    entity_class.__name__,
                    connected_user.get("sub") if connected_user else None,
                    info.context.webservice_name
                )

            async def resolve_node():
                node = await resolver(self, *args, info=info, **kwargs)

                # check if the object is the same type of ensure type (allow None for Optional types)
                if node is not None and not isinstance(node, ensure_type_):
                    raise ValueError(
                        "Wrong node type '%s'. (Expected: '%s')" % (
                            node.__class__.__name__,
                            ensure_type_.__name__
                        )
                    )

                return node

            async def wrapped() -> ServiceNodeMixin:
                if has_session:
                    # Check if session already exists in context (from DatabaseSessionExtension)
                    existing_session = getattr(info.context, 'session', None)
                    if existing_session is not None:
                        # Use existing session from context
                        return await resolve_node()
                    else:
                        # Create new session if none exists
                        async with ensure_type_.app_manager.database.get_session() as session:
                            info.context.session = session
                            return await resolve_node()
                else:
                    return await resolve_node()

            return await wrapped()

        inner_resolver.__name__ = resolver.__name__
        inner_resolver.__qualname__ = resolver.__qualname__
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
        register=register,
        options=options
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
        options: dict = None
) -> Any:
    effective_ensure_type = ensure_type.get_effective_node()

    def wrapper(resolver: Callable):
        sig = inspect.signature(resolver)
        parameter_value_list = list(sig.parameters.values())

        # check if order by schema type exist for the specified node
        order_by_type = getattr(effective_ensure_type, "order_by_type", None)

        # if not the case create it and save it to make it reusable
        if order_by_type is None and len(effective_ensure_type.order_by_attribute_map.keys()) > 0:
            class_str = """class %s :\n""" % (effective_ensure_type.__name__ + "OderByType")

            for key in effective_ensure_type.order_by_attribute_map.keys():
                class_str += """   %s : bool | None = strawberry.UNSET\n""" % key

            class_str += """order_by_type = %s""" % (effective_ensure_type.__name__ + "OderByType")

            exec(class_str)

            loc = {}
            exec(class_str, globals(), loc)
            order_by_type = loc['order_by_type']
            effective_ensure_type.order_by_type = order_by_type

        # add it to the webservice parameters
        if order_by_type is not None:
            # Build dynamic description with available sort fields
            sort_fields = list(effective_ensure_type.order_by_attribute_map.keys())
            order_by_description = f"Sort results by field. Available: {', '.join(sort_fields)}. Use true for ASC, false for DESC"

            parameter_value_list.append(
                inspect.Parameter(
                    "order_by",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Annotated[
                        strawberry.input(order_by_type, one_of=True) | None,
                        strawberry.argument(description=order_by_description)
                    ],
                    default=None
                )
            )

        parameter_value_list.append(
            inspect.Parameter(
                "limit",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[int | None, strawberry.argument(description="Maximum number of results to return")],
                default=None
            )
        )

        # overwrite webservice to compute order by if needed
        async def inner_resolver(*args, info: Info, **kwargs):
            info.context.app_manager = effective_ensure_type.app_manager

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
                for key in effective_ensure_type.order_by_attribute_map.keys():
                    value = getattr(order_by, key, None)
                    if isinstance(value, bool):
                        column = effective_ensure_type.order_by_attribute_map[key]
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
        inner_resolver.__qualname__ = resolver.__qualname__
        inner_resolver.__module__ = resolver.__module__

        field_config = create_strawberry_field_config(
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
        return _apply_webservice_config(field, is_public, enabled, access_levels, is_licenced, allow_override, description, None, options)

    return wrapper
