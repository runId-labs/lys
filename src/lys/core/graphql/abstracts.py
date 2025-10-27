import sys
from abc import abstractmethod
from typing import Any, Optional, cast, Self

from graphql.pyutils import AwaitableOrValue
from sqlalchemy import Select
from strawberry.relay import NodeType, Edge
from strawberry.relay.utils import SliceMetadata
from strawberry.types import get_object_definition
from strawberry.types.base import StrawberryContainer

from lys.core.contexts import Info
from lys.core.graphql.types import LysPageInfo


class AbstractListConnection:
    @classmethod
    @abstractmethod
    def resolve_node(cls, node: Any, *, info: Info, **kwargs: Any) -> NodeType:
        raise NotImplementedError

    @classmethod
    def before_compute_returning_list(cls, info: Info, before: Optional[str],
                                      after: Optional[str], first: Optional[int], last: Optional[int]):
        slice_metadata = SliceMetadata.from_arguments(info, before=before, after=after, first=first, last=last)

        type_def = get_object_definition(cls)
        assert type_def
        field_def = type_def.get_field("edges")
        assert field_def

        field_ = field_def.resolve_type(type_definition=type_def)
        while isinstance(field_, StrawberryContainer):
            field_ = field_.of_type
        edge_class = cast(Edge[NodeType], field_)

        return slice_metadata, edge_class

    @classmethod
    def prepare_returning_list(cls, slice_metadata: SliceMetadata,edges: list[Edge], last: Optional[int],
                               total_count: int):
        has_previous_page = slice_metadata.start > 0
        if slice_metadata.expected is not None and len(edges) == slice_metadata.expected + 1:
            # Remove the over fetched result
            edges = edges[:-1]
            has_next_page = True
        elif slice_metadata.end == sys.maxsize:
            # Last was asked without any after/before
            assert last is not None
            original_len = len(edges)
            edges = edges[-last:]
            has_next_page = False
            has_previous_page = len(edges) != original_len
        else:
            has_next_page = False

        return cls(
            edges=edges,
            page_info=LysPageInfo(
                total_count=total_count,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
                has_previous_page=has_previous_page,
                has_next_page=has_next_page,
            ),
        )

    @classmethod
    @abstractmethod
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
        raise NotImplementedError
