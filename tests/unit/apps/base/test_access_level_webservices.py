"""
Unit tests for base access_level module webservices.

Tests GraphQL query structure.
"""

import pytest
import inspect


class TestAccessLevelQuery:
    """Tests for AccessLevelQuery."""

    def test_query_exists(self):
        """Test AccessLevelQuery class exists."""
        from lys.apps.base.modules.access_level.webservices import AccessLevelQuery
        assert AccessLevelQuery is not None

    def test_query_inherits_from_query(self):
        """Test AccessLevelQuery inherits from Query."""
        from lys.apps.base.modules.access_level.webservices import AccessLevelQuery
        from lys.core.graphql.types import Query
        assert issubclass(AccessLevelQuery, Query)

    def test_query_has_strawberry_type_decorator(self):
        """Test AccessLevelQuery is decorated with strawberry.type."""
        from lys.apps.base.modules.access_level.webservices import AccessLevelQuery
        assert hasattr(AccessLevelQuery, "__strawberry_definition__")

    def test_all_access_levels_method_exists(self):
        """Test all_access_levels method exists."""
        from lys.apps.base.modules.access_level.webservices import AccessLevelQuery
        assert hasattr(AccessLevelQuery, "all_access_levels")

    def test_all_access_levels_is_async(self):
        """Test all_access_levels is async."""
        from lys.apps.base.modules.access_level.webservices import AccessLevelQuery
        assert inspect.iscoroutinefunction(AccessLevelQuery.all_access_levels)

    def test_all_access_levels_signature(self):
        """Test all_access_levels method signature."""
        from lys.apps.base.modules.access_level.webservices import AccessLevelQuery

        sig = inspect.signature(AccessLevelQuery.all_access_levels)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "info" in params
        assert "enabled" in params
