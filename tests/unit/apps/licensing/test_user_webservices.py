"""
Unit tests for licensing user webservices.

Tests the structure and method signatures of LicensingUserQuery
and LicensingUserMutation without requiring a database or external services.

Note: Webservice modules use a singleton registry that can raise ValueError
when multiple apps register webservices with the same name.
We handle this by catching import errors and using sys.modules.
"""
import inspect
import sys

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")


def _import_licensing_user_webservices():
    """Import licensing user webservices module, handling registry conflicts."""
    module_name = "lys.apps.licensing.modules.user.webservices"
    if module_name in sys.modules:
        return sys.modules[module_name]
    try:
        import importlib
        return importlib.import_module(module_name)
    except ValueError:
        return sys.modules.get(module_name)


class TestLicensingUserQuery:
    """Tests for LicensingUserQuery webservice class structure and methods."""

    def test_class_exists(self):
        """Test LicensingUserQuery class can be imported."""
        mod = _import_licensing_user_webservices()
        assert hasattr(mod, "LicensingUserQuery")

    def test_has_all_client_users_method(self):
        """Test LicensingUserQuery has all_client_users method."""
        mod = _import_licensing_user_webservices()
        assert hasattr(mod.LicensingUserQuery, "all_client_users")

    def test_all_client_users_is_async(self):
        """Test all_client_users is an async method."""
        mod = _import_licensing_user_webservices()
        assert inspect.iscoroutinefunction(mod.LicensingUserQuery.all_client_users)


class TestLicensingUserMutation:
    """Tests for LicensingUserMutation webservice class structure and methods."""

    def test_class_exists(self):
        """Test LicensingUserMutation class can be imported."""
        mod = _import_licensing_user_webservices()
        assert hasattr(mod, "LicensingUserMutation")

    def test_has_add_client_user_to_subscription_method(self):
        """Test LicensingUserMutation has add_client_user_to_subscription method."""
        mod = _import_licensing_user_webservices()
        assert hasattr(mod.LicensingUserMutation, "add_client_user_to_subscription")

    def test_add_client_user_to_subscription_is_async(self):
        """Test add_client_user_to_subscription is an async method."""
        mod = _import_licensing_user_webservices()
        assert inspect.iscoroutinefunction(mod.LicensingUserMutation.add_client_user_to_subscription)

    def test_has_remove_client_user_from_subscription_method(self):
        """Test LicensingUserMutation has remove_client_user_from_subscription method."""
        mod = _import_licensing_user_webservices()
        assert hasattr(mod.LicensingUserMutation, "remove_client_user_from_subscription")

    def test_remove_client_user_from_subscription_is_async(self):
        """Test remove_client_user_from_subscription is an async method."""
        mod = _import_licensing_user_webservices()
        assert inspect.iscoroutinefunction(mod.LicensingUserMutation.remove_client_user_from_subscription)
