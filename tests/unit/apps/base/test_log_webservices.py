"""
Unit tests for base log module webservices.

Tests GraphQL query structure.
"""

import pytest
import inspect


class TestLogQuery:
    """Tests for LogQuery."""

    def test_query_exists(self):
        """Test LogQuery class exists."""
        from lys.apps.base.modules.log.webservices import LogQuery
        assert LogQuery is not None

    def test_query_inherits_from_query(self):
        """Test LogQuery inherits from Query."""
        from lys.apps.base.modules.log.webservices import LogQuery
        from lys.core.graphql.types import Query
        assert issubclass(LogQuery, Query)

    def test_query_has_strawberry_type_decorator(self):
        """Test LogQuery is decorated with strawberry.type."""
        from lys.apps.base.modules.log.webservices import LogQuery
        assert hasattr(LogQuery, "__strawberry_definition__")

    def test_all_logs_method_exists(self):
        """Test all_logs method exists."""
        from lys.apps.base.modules.log.webservices import LogQuery
        assert hasattr(LogQuery, "all_logs")

    def test_all_logs_is_async(self):
        """Test all_logs is async."""
        from lys.apps.base.modules.log.webservices import LogQuery
        assert inspect.iscoroutinefunction(LogQuery.all_logs)

    def test_all_logs_signature(self):
        """Test all_logs method signature."""
        from lys.apps.base.modules.log.webservices import LogQuery

        sig = inspect.signature(LogQuery.all_logs)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "info" in params
        assert "start_date" in params
        assert "end_date" in params
        assert "file_name" in params

    def test_all_logs_parameters_are_optional(self):
        """Test all_logs filter parameters have default None."""
        from lys.apps.base.modules.log.webservices import LogQuery

        sig = inspect.signature(LogQuery.all_logs)
        params = sig.parameters

        assert params["start_date"].default is None
        assert params["end_date"].default is None
        assert params["file_name"].default is None
