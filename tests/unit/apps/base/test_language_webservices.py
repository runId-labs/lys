"""
Unit tests for base language module webservices.

Tests GraphQL query structure.
"""

import pytest
import inspect


class TestLanguageQuery:
    """Tests for LanguageQuery."""

    def test_query_exists(self):
        """Test LanguageQuery class exists."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        assert LanguageQuery is not None

    def test_query_inherits_from_query(self):
        """Test LanguageQuery inherits from Query."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        from lys.core.graphql.types import Query
        assert issubclass(LanguageQuery, Query)

    def test_query_has_strawberry_type_decorator(self):
        """Test LanguageQuery is decorated with strawberry.type."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        assert hasattr(LanguageQuery, "__strawberry_definition__")

    def test_query_has_docstring(self):
        """Test LanguageQuery has a docstring."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        assert LanguageQuery.__doc__ is not None

    def test_all_languages_method_exists(self):
        """Test all_languages method exists."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        assert hasattr(LanguageQuery, "all_languages")

    def test_all_languages_is_async(self):
        """Test all_languages is async."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        assert inspect.iscoroutinefunction(LanguageQuery.all_languages)

    def test_all_languages_signature(self):
        """Test all_languages method signature."""
        from lys.apps.base.modules.language.webservices import LanguageQuery

        sig = inspect.signature(LanguageQuery.all_languages)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "info" in params
        assert "enabled" in params

    def test_all_languages_returns_select(self):
        """Test all_languages method returns Select type annotation."""
        from lys.apps.base.modules.language.webservices import LanguageQuery
        import inspect

        sig = inspect.signature(LanguageQuery.all_languages)
        # Method should return Select
        assert "Select" in str(sig.return_annotation)
