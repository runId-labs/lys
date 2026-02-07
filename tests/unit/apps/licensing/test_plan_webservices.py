"""
Unit tests for licensing plan webservices.

Tests the structure and method signatures of LicensePlanQuery
without requiring a database or external services.

Note: Webservice modules use a singleton registry that can raise ValueError
when multiple apps register webservices with the same name.
We handle this by catching import errors and using sys.modules.
"""
import inspect
import sys

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")


def _import_plan_webservices():
    """Import licensing plan webservices module, handling registry conflicts."""
    module_name = "lys.apps.licensing.modules.plan.webservices"
    if module_name in sys.modules:
        return sys.modules[module_name]
    try:
        import importlib
        return importlib.import_module(module_name)
    except ValueError:
        return sys.modules.get(module_name)


class TestLicensePlanQuery:
    """Tests for LicensePlanQuery webservice class structure and methods."""

    def test_class_exists(self):
        """Test LicensePlanQuery class can be imported."""
        mod = _import_plan_webservices()
        assert hasattr(mod, "LicensePlanQuery")

    def test_has_all_active_license_plans_method(self):
        """Test LicensePlanQuery has all_active_license_plans method."""
        mod = _import_plan_webservices()
        assert hasattr(mod.LicensePlanQuery, "all_active_license_plans")

    def test_all_active_license_plans_is_async(self):
        """Test all_active_license_plans is an async method."""
        mod = _import_plan_webservices()
        assert inspect.iscoroutinefunction(mod.LicensePlanQuery.all_active_license_plans)
