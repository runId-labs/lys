"""
GraphQL subscription field decorator for lys framework.

Provides lys_subscription decorator for creating SSE-based subscriptions
with permission handling and webservice registration.
"""
import dataclasses
import inspect
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type, AsyncIterator

import strawberry
from strawberry.extensions import FieldExtension

from lys.core.contexts import Info
from lys.core.graphql.nodes import ServiceNodeMixin
from lys.core.permissions import generate_webservice_permission
from lys.core.registries import AppRegistry, register_webservice
from lys.core.utils.webservice import WebserviceIsPublicType, format_filed_description


def lys_subscription(
        ensure_type: Type[ServiceNodeMixin],
        is_public: WebserviceIsPublicType = False,
        enabled: bool = True,
        access_levels: List[str] = None,
        is_licenced: bool = True,
        allow_override: bool = False,
        name: Optional[str] = None,
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
    """
    Decorator for GraphQL subscription fields.

    Creates a subscription with permission handling, webservice registration,
    and runtime type validation for yielded nodes.

    Args:
        ensure_type: The node type that must be yielded (validated at runtime)
        is_public: Whether the subscription is publicly accessible
        enabled: Whether the subscription is enabled
        access_levels: Required access levels for the subscription
        is_licenced: Whether the subscription requires a valid license
        allow_override: Whether this subscription can be overridden
        name: GraphQL field name (defaults to function name)
        description: Field description
        deprecation_reason: If set, marks the field as deprecated
        register: Custom AppRegistry to use
        options: Additional options

    Usage:
        @lys_subscription(ensure_type=SignalNode, is_public=True)
        async def signals(self, info: Info, channel: str) -> AsyncIterator[SignalNode]:
            async for message in signal_service.subscribe(channel):
                yield SignalNode(...)
    """
    effective_ensure_type = ensure_type.get_effective_node()

    def wrapper(resolver: Callable):
        async def inner_resolver(self, *args, info: Info, **kwargs) -> AsyncIterator[ServiceNodeMixin]:
            async for node in resolver(self, *args, info=info, **kwargs):
                if node is not None and not isinstance(node, effective_ensure_type):
                    raise ValueError(
                        f"Wrong node type '{node.__class__.__name__}'. "
                        f"Expected: '{effective_ensure_type.__name__}'"
                    )
                yield node

        inner_resolver.__name__ = resolver.__name__
        inner_resolver.__qualname__ = resolver.__qualname__
        inner_resolver.__module__ = resolver.__module__
        inner_resolver.__signature__ = inspect.signature(resolver)

        field = strawberry.subscription(
            resolver=inner_resolver,
            name=name,
            description=format_filed_description(description, is_public, access_levels, is_licenced),
            permission_classes=[generate_webservice_permission(resolver.__name__)],
            deprecation_reason=deprecation_reason,
            default=default,
            default_factory=default_factory,
            metadata=metadata,
            directives=directives,
            extensions=extensions,
            graphql_type=graphql_type,
            init=init,
        )

        # Register as webservice for access control
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

    return wrapper
