import dataclasses
from typing import Optional, Callable, List, Any, Union, Mapping, Sequence, Type, cast

from strawberry import relay
from strawberry.annotation import StrawberryAnnotation
from strawberry.extensions import FieldExtension
from strawberry.relay import Connection, ConnectionExtension
from strawberry.relay.exceptions import RelayWrongAnnotationError
from strawberry.types.arguments import StrawberryArgument
from strawberry.types.field import StrawberryField

from lys.core.graphql.fields import lys_connection_field
from lys.core.graphql.nodes import EntityNode
from lys.core.utils.webservice import WebserviceIsPublicType


class LysConnectionExtension(ConnectionExtension):
    def apply(self, field: StrawberryField) -> None:
        field.arguments = [
            *field.arguments,
            StrawberryArgument(
                python_name="before",
                graphql_name=None,
                type_annotation=StrawberryAnnotation(Optional[str]),
                description=(
                    "Returns the items in the list that come before the "
                    "specified cursor."
                ),
                default=None,
            ),
            StrawberryArgument(
                python_name="after",
                graphql_name=None,
                type_annotation=StrawberryAnnotation(Optional[str]),
                description=(
                    "Returns the items in the list that come after the "
                    "specified cursor."
                ),
                default=None,
            ),
            StrawberryArgument(
                python_name="first",
                graphql_name=None,
                type_annotation=StrawberryAnnotation(Optional[int]),
                description="Returns the first n items from the list.",
                default=None,
            ),
            StrawberryArgument(
                python_name="last",
                graphql_name=None,
                type_annotation=StrawberryAnnotation(Optional[int]),
                description=(
                    "Returns the items in the list that come after the "
                    "specified cursor."
                ),
                default=None,
            ),
        ]

        f_type = field.type
        if not isinstance(f_type, type) or not issubclass(f_type, Connection):
            raise RelayWrongAnnotationError(field.name, cast(type, field.origin))

        assert field.base_resolver
        self.connection_type = cast(Type[Connection[relay.Node]], field.type)


def lys_connection(
        ensure_type: Type[EntityNode],
        *,
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
        extensions: List[FieldExtension] = ()
) -> Any:
    return lys_connection_field(
        ensure_type=ensure_type,
        is_public=is_public,
        enabled=enabled,
        access_levels=access_levels,
        is_licenced=is_licenced,
        allow_override=allow_override,
        name=name,
        description=description,
        is_subscription=is_subscription,
        deprecation_reason=deprecation_reason,
        default=default,
        default_factory=default_factory,
        metadata=metadata,
        directives=directives or (),
        graphql_type=ensure_type.build_list_connection(),
        extensions=[*extensions, LysConnectionExtension()],
    )