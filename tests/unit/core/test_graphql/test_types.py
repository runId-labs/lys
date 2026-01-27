"""
Unit tests for core graphql types module.

Tests GraphQL type classes.
"""

import pytest


class TestLysPageInfo:
    """Tests for LysPageInfo class."""

    def test_class_exists(self):
        """Test LysPageInfo class exists."""
        from lys.core.graphql.types import LysPageInfo
        assert LysPageInfo is not None

    def test_has_total_count_field(self):
        """Test LysPageInfo has total_count field."""
        from lys.core.graphql.types import LysPageInfo
        assert "total_count" in LysPageInfo.__annotations__

    def test_inherits_from_page_info(self):
        """Test LysPageInfo inherits from strawberry PageInfo."""
        from lys.core.graphql.types import LysPageInfo
        from strawberry.relay import PageInfo
        assert issubclass(LysPageInfo, PageInfo)
