"""
Unit tests for core interfaces permissions module.

Tests PermissionInterface abstract class.
"""

import pytest


class TestPermissionInterface:
    """Tests for PermissionInterface class."""

    def test_module_exists(self):
        """Test permissions interface module exists."""
        from lys.core.interfaces import permissions
        assert permissions is not None

    def test_module_can_be_imported(self):
        """Test permissions interface module can be imported."""
        import importlib
        try:
            module = importlib.import_module("lys.core.interfaces.permissions")
            imported = True
        except ImportError:
            imported = False
        assert imported
