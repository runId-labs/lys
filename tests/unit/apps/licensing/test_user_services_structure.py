"""
Unit tests for licensing user services structure.

Tests class structure and method signatures of licensing UserService.
"""

import inspect

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.modules.user.services import UserService
from lys.apps.organization.modules.user.services import UserService as OrgUserService


class TestUserServiceStructure:
    """Tests for licensing UserService class structure."""

    def test_class_exists(self):
        assert UserService is not None

    def test_inherits_from_org_user_service(self):
        assert issubclass(UserService, OrgUserService)

    def test_has_add_to_subscription(self):
        assert hasattr(UserService, "add_to_subscription")

    def test_has_remove_from_subscription(self):
        assert hasattr(UserService, "remove_from_subscription")


class TestUserServiceAsyncMethods:
    """Tests for async method signatures."""

    def test_add_to_subscription_is_async(self):
        assert inspect.iscoroutinefunction(UserService.add_to_subscription)

    def test_remove_from_subscription_is_async(self):
        assert inspect.iscoroutinefunction(UserService.remove_from_subscription)


class TestUserServiceSignatures:
    """Tests for method parameter signatures."""

    def test_add_to_subscription_params(self):
        sig = inspect.signature(UserService.add_to_subscription)
        params = list(sig.parameters.keys())
        assert "user" in params
        assert "session" in params
        assert "background_tasks" in params

    def test_remove_from_subscription_params(self):
        sig = inspect.signature(UserService.remove_from_subscription)
        params = list(sig.parameters.keys())
        assert "user" in params
        assert "session" in params
        assert "background_tasks" in params
