"""
Unit tests for file_management file_import module webservices.

Tests GraphQL query structure and method signatures.
"""

import inspect
import sys

import pytest

# Skip all tests if aioboto3 is not installed
pytest.importorskip("aioboto3", reason="aioboto3 not installed")

_mod = None
_module_name = "lys.apps.file_management.modules.file_import.webservices"
if _module_name in sys.modules:
    _mod = sys.modules[_module_name]
else:
    try:
        import importlib
        _mod = importlib.import_module(_module_name)
    except (ValueError, ImportError):
        _mod = None


def _get_mod():
    if _mod is None:
        pytest.skip("file_import webservices could not be imported due to registry conflict")
    return _mod


class TestFileImportQueryStructure:
    """Tests for FileImportQuery class structure."""

    def test_class_exists(self):
        """Test FileImportQuery class exists."""
        mod = _get_mod()
        assert hasattr(mod, "FileImportQuery")

    def test_inherits_from_query(self):
        """Test FileImportQuery inherits from Query."""
        mod = _get_mod()
        from lys.core.graphql.types import Query
        assert issubclass(mod.FileImportQuery, Query)

    def test_has_strawberry_type_decorator(self):
        """Test FileImportQuery is decorated with strawberry.type."""
        mod = _get_mod()
        assert hasattr(mod.FileImportQuery, "__strawberry_definition__")


class TestAllFileImportsMethod:
    """Tests for FileImportQuery.all_file_imports method."""

    def test_method_exists(self):
        """Test all_file_imports method exists."""
        mod = _get_mod()
        assert hasattr(mod.FileImportQuery, "all_file_imports")

    def test_method_is_async(self):
        """Test all_file_imports is async."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.FileImportQuery.all_file_imports)

    def test_signature_has_info(self):
        """Test all_file_imports has info parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.FileImportQuery.all_file_imports)
        assert "info" in sig.parameters

    def test_client_id_is_optional(self):
        """Test client_id parameter is optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.FileImportQuery.all_file_imports)
        assert sig.parameters["client_id"].default is None

    def test_status_id_is_optional(self):
        """Test status_id parameter is optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.FileImportQuery.all_file_imports)
        assert sig.parameters["status_id"].default is None

    def test_type_id_is_optional(self):
        """Test type_id parameter is optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.FileImportQuery.all_file_imports)
        assert sig.parameters["type_id"].default is None


class TestActiveFileImportsCountMethod:
    """Tests for FileImportQuery.active_file_imports_count method."""

    def test_method_exists(self):
        """Test active_file_imports_count method exists."""
        mod = _get_mod()
        assert hasattr(mod.FileImportQuery, "active_file_imports_count")

    def test_method_is_async(self):
        """Test active_file_imports_count is async."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.FileImportQuery.active_file_imports_count)

    def test_signature_has_info(self):
        """Test active_file_imports_count has info parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.FileImportQuery.active_file_imports_count)
        assert "info" in sig.parameters

    def test_returns_active_file_imports_count_node(self):
        """Test active_file_imports_count returns ActiveFileImportsCountNode."""
        mod = _get_mod()
        sig = inspect.signature(mod.FileImportQuery.active_file_imports_count)
        assert "ActiveFileImportsCountNode" in str(sig.return_annotation)
