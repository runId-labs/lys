import dataclasses
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Literal, Type

from strawberry import relay
from strawberry.extensions import FieldExtension

from lys.core.consts.errors import NOT_FOUND_ERROR
from lys.core.contexts import Info
from lys.core.entities import Entity
from lys.core.errors import LysError
from lys.core.graphql.fields import lys_typed_field
from lys.core.graphql.nodes import EntityNode, SuccessNode
from lys.core.utils.access import get_db_object_and_check_access
from lys.core.utils.webservice import WebserviceIsPublicType


def _delete_resolver_generator(resolver: Callable, ensure_type: Type[EntityNode]):
    async def inner_resolver(self, id: relay.GlobalID, info: Info) -> SuccessNode:
        info.context.service_class = ensure_type.service_class

        async def wrapped() -> SuccessNode:
            async with ensure_type.app_manager.database.get_session() as session:
                info.context.session = session

                entity_obj: Optional[Entity] = await get_db_object_and_check_access(
                    id.node_id,
                    ensure_type.entity_class,
                    info.context,
                    session=session
                )

                if not entity_obj:
                    raise LysError(
                        NOT_FOUND_ERROR,
                        "_delete_resolver_generator: Unknown entity with type '%s' and id '%s'" % (
                            ensure_type.entity_class,
                            id.node_id
                        )
                    )

                # update the object with the resolver
                await resolver(self, obj=entity_obj, info=info)
                await session.delete(entity_obj)

            return SuccessNode(
                succeed=True
            )

        return await wrapped()

    inner_resolver.__name__ = resolver.__name__
    inner_resolver.__module__ = resolver.__module__


    return inner_resolver


def lys_delete(
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

    description = (description if description is not None else "") + "\n" + (
        "PUBLIC"
        if is_public
        else (
            f"ACCESS LEVELS: {", ".join([access_level for access_level in access_levels])}"
            if (access_levels is not None and len(access_levels) > 0)
            else "ONLY FOR SUPER USER"
        )
    ) + "\n" + ("UNDER LICENCE" if is_licenced else "LICENCE FREE")

    def wrapper(resolver: Callable):
        field = lys_typed_field(
            ensure_type=ensure_type,
            resolver_wrapper=_delete_resolver_generator,
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

        field.base_resolver.type_annotation = SuccessNode

        return field

    return wrapper
