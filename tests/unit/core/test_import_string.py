"""
Unit tests for core utils import_string module.
"""
import pytest

from lys.core.utils.import_string import import_string


class TestImportString:
    """Tests for import_string function."""

    def test_import_valid_dotted_path(self):
        """Test importing a class from a valid dotted path."""
        result = import_string("lys.core.configs.AppSettings")
        from lys.core.configs import AppSettings
        assert result is AppSettings

    def test_import_valid_function(self):
        """Test importing a function from a valid dotted path."""
        result = import_string("lys.core.utils.import_string.import_string")
        assert result is import_string

    def test_import_no_dot_raises_import_error(self):
        """Test that a path without dots raises ImportError."""
        with pytest.raises(ImportError, match="is not a valid dotted path"):
            import_string("nodots")

    def test_import_empty_string_raises_import_error(self):
        """Test that an empty string raises ImportError."""
        with pytest.raises(ImportError, match="is not a valid dotted path"):
            import_string("")

    def test_import_valid_module_missing_attribute(self):
        """Test that a valid module but missing attribute raises ImportError."""
        with pytest.raises(ImportError, match="has no attribute"):
            import_string("lys.core.configs.NonExistentClass")

    def test_import_invalid_module_raises_error(self):
        """Test that an invalid module path raises an error."""
        with pytest.raises(Exception):
            import_string("totally.fake.module.ClassName")
