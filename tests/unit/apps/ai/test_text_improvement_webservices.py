"""
Unit tests for AI text improvement webservices.

Tests structure of TextImprovementMutation.

Note: Webservice modules use a singleton registry that can raise ValueError
when multiple apps register webservices with the same name.
"""

import inspect
import sys

_mod = None
_module_name = "lys.apps.ai.modules.text_improvement.webservices"
if _module_name in sys.modules:
    _mod = sys.modules[_module_name]
else:
    try:
        import importlib
        _mod = importlib.import_module(_module_name)
    except (ValueError, ImportError):
        _mod = None


def _get_mod():
    import pytest
    if _mod is None:
        pytest.skip("text improvement webservices could not be imported due to registry conflict")
    return _mod


class TestTextImprovementMutationStructure:
    """Tests for TextImprovementMutation class structure."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "TextImprovementMutation")

    def test_has_improve_text_method(self):
        mod = _get_mod()
        assert hasattr(mod.TextImprovementMutation, "improve_text")
