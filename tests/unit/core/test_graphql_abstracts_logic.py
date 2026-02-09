"""
Unit tests for core graphql abstracts module logic.

Tests AbstractListConnection.prepare_returning_list() method.
"""

import sys
from unittest.mock import MagicMock

from lys.core.graphql.abstracts import AbstractListConnection


def _make_edge(cursor):
    edge = MagicMock()
    edge.cursor = cursor
    return edge


class ConcreteConnection(AbstractListConnection):

    def __init__(self, edges, page_info):
        self.edges = edges
        self.page_info = page_info

    @classmethod
    def resolve_node(cls, node, *, info, **kwargs):
        return node

    @classmethod
    def resolve_connection(cls, stmt, *, info, **kwargs):
        raise NotImplementedError


class TestPrepareReturningList:

    def test_normal_case_no_overflow(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 0
        slice_metadata.expected = 10
        slice_metadata.end = 10

        edges = [_make_edge(f"cursor_{i}") for i in range(5)]

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=None, total_count=5
        )
        assert result.page_info.has_next_page is False
        assert result.page_info.has_previous_page is False
        assert len(result.edges) == 5
        assert result.page_info.total_count == 5

    def test_overflow_case_trims_and_has_next(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 0
        slice_metadata.expected = 3
        slice_metadata.end = 3

        edges = [_make_edge(f"cursor_{i}") for i in range(4)]

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=None, total_count=10
        )
        assert result.page_info.has_next_page is True
        assert result.page_info.has_previous_page is False
        assert len(result.edges) == 3

    def test_has_previous_page_when_start_positive(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 5
        slice_metadata.expected = 10
        slice_metadata.end = 15

        edges = [_make_edge(f"cursor_{i}") for i in range(3)]

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=None, total_count=8
        )
        assert result.page_info.has_previous_page is True
        assert result.page_info.has_next_page is False

    def test_last_parameter_slices_edges(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 0
        slice_metadata.expected = None
        slice_metadata.end = sys.maxsize

        edges = [_make_edge(f"cursor_{i}") for i in range(5)]

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=3, total_count=5
        )
        assert len(result.edges) == 3
        assert result.page_info.has_next_page is False
        assert result.page_info.has_previous_page is True

    def test_last_parameter_no_truncation(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 0
        slice_metadata.expected = None
        slice_metadata.end = sys.maxsize

        edges = [_make_edge(f"cursor_{i}") for i in range(2)]

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=5, total_count=2
        )
        assert len(result.edges) == 2
        assert result.page_info.has_previous_page is False
        assert result.page_info.has_next_page is False

    def test_empty_edges(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 0
        slice_metadata.expected = 10
        slice_metadata.end = 10

        edges = []

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=None, total_count=0
        )
        assert len(result.edges) == 0
        assert result.page_info.start_cursor is None
        assert result.page_info.end_cursor is None
        assert result.page_info.has_next_page is False
        assert result.page_info.has_previous_page is False

    def test_start_and_end_cursors_set(self):
        slice_metadata = MagicMock()
        slice_metadata.start = 0
        slice_metadata.expected = 10
        slice_metadata.end = 10

        edges = [_make_edge("first"), _make_edge("middle"), _make_edge("last")]

        result = ConcreteConnection.prepare_returning_list(
            slice_metadata, edges, last=None, total_count=3
        )
        assert result.page_info.start_cursor == "first"
        assert result.page_info.end_cursor == "last"
