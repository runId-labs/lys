"""
Unit tests for licensing mollie webservices.

Tests structure of MollieMutation and helper functions.
"""

import inspect
import sys

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

_mod = None
_module_name = "lys.apps.licensing.modules.mollie.webservices"
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
        pytest.skip("mollie webservices could not be imported due to registry conflict")
    return _mod


class TestMollieWebservicesModuleAttributes:
    """Tests for module-level attributes."""

    def test_module_has_router(self):
        mod = _get_mod()
        assert hasattr(mod, "router")

    def test_router_has_prefix(self):
        mod = _get_mod()
        assert mod.router.prefix == "/webhooks"

    def test_has_get_app_manager_function(self):
        mod = _get_mod()
        assert hasattr(mod, "get_app_manager")
        assert callable(mod.get_app_manager)

    def test_has_get_client_for_user_function(self):
        mod = _get_mod()
        assert hasattr(mod, "get_client_for_user")

    def test_get_client_for_user_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.get_client_for_user)

    def test_has_mollie_webhook_function(self):
        mod = _get_mod()
        assert hasattr(mod, "mollie_webhook")

    def test_mollie_webhook_is_async(self):
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.mollie_webhook)


class TestMollieMutationStructure:
    """Tests for MollieMutation class structure."""

    def test_class_exists(self):
        mod = _get_mod()
        assert hasattr(mod, "MollieMutation")

    def test_has_subscribe_to_plan(self):
        mod = _get_mod()
        assert hasattr(mod.MollieMutation, "subscribe_to_plan")

    def test_has_cancel_subscription(self):
        mod = _get_mod()
        assert hasattr(mod.MollieMutation, "cancel_subscription")
