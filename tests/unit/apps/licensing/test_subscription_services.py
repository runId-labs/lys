"""
Unit tests for SubscriptionService class structure, method existence, and signatures.

Tests verify the service interface without requiring a database or external services.
"""
import inspect

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestSubscriptionServiceClass:
    """Tests for SubscriptionService class existence and inheritance."""

    def test_class_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert SubscriptionService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from lys.core.services import EntityService
        assert issubclass(SubscriptionService, EntityService)


class TestSubscriptionServiceGetClientSubscription:
    """Tests for SubscriptionService.get_client_subscription method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "get_client_subscription")

    def test_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert inspect.iscoroutinefunction(SubscriptionService.get_client_subscription)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "get_client_subscription")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.get_client_subscription)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "session" in params


class TestSubscriptionServiceCreateSubscription:
    """Tests for SubscriptionService.create_subscription method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "create_subscription")

    def test_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert inspect.iscoroutinefunction(SubscriptionService.create_subscription)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "create_subscription")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.create_subscription)
        params = sig.parameters
        assert "client_id" in params
        assert "plan_version_id" in params
        assert "session" in params
        assert "provider_subscription_id" in params
        assert params["provider_subscription_id"].default is None


class TestSubscriptionServiceChangePlan:
    """Tests for SubscriptionService.change_plan method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "change_plan")

    def test_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert inspect.iscoroutinefunction(SubscriptionService.change_plan)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "change_plan")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.change_plan)
        params = sig.parameters
        assert "client_id" in params
        assert "new_plan_version_id" in params
        assert "session" in params
        assert "immediate" in params
        assert params["immediate"].default is True


class TestSubscriptionServiceApplyPendingChange:
    """Tests for SubscriptionService.apply_pending_change method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "apply_pending_change")

    def test_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert inspect.iscoroutinefunction(SubscriptionService.apply_pending_change)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "apply_pending_change")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.apply_pending_change)
        params = list(sig.parameters.keys())
        assert "subscription_id" in params
        assert "session" in params


class TestSubscriptionServiceUserManagement:
    """Tests for SubscriptionService user management methods."""

    def test_is_user_in_subscription_exists_and_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "is_user_in_subscription")
        assert inspect.iscoroutinefunction(SubscriptionService.is_user_in_subscription)

    def test_is_user_in_subscription_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.is_user_in_subscription)
        params = list(sig.parameters.keys())
        assert "subscription_id" in params
        assert "user_id" in params
        assert "session" in params

    def test_add_user_to_subscription_exists_and_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "add_user_to_subscription")
        assert inspect.iscoroutinefunction(SubscriptionService.add_user_to_subscription)

    def test_add_user_to_subscription_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "add_user_to_subscription")
        assert isinstance(attr, classmethod)

    def test_add_user_to_subscription_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.add_user_to_subscription)
        params = list(sig.parameters.keys())
        assert "subscription_id" in params
        assert "user_id" in params
        assert "session" in params

    def test_remove_user_from_subscription_exists_and_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "remove_user_from_subscription")
        assert inspect.iscoroutinefunction(SubscriptionService.remove_user_from_subscription)

    def test_remove_user_from_subscription_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "remove_user_from_subscription")
        assert isinstance(attr, classmethod)

    def test_remove_user_from_subscription_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.remove_user_from_subscription)
        params = list(sig.parameters.keys())
        assert "subscription_id" in params
        assert "user_id" in params
        assert "session" in params

    def test_get_subscription_user_count_exists_and_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "get_subscription_user_count")
        assert inspect.iscoroutinefunction(SubscriptionService.get_subscription_user_count)

    def test_get_subscription_user_count_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.get_subscription_user_count)
        params = list(sig.parameters.keys())
        assert "subscription_id" in params
        assert "session" in params

    def test_is_user_licensed_exists_and_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "is_user_licensed")
        assert inspect.iscoroutinefunction(SubscriptionService.is_user_licensed)

    def test_is_user_licensed_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "is_user_licensed")
        assert isinstance(attr, classmethod)

    def test_is_user_licensed_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.is_user_licensed)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "session" in params


class TestSubscriptionServiceSubscribeToPlan:
    """Tests for SubscriptionService.subscribe_to_plan method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "subscribe_to_plan")

    def test_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert inspect.iscoroutinefunction(SubscriptionService.subscribe_to_plan)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "subscribe_to_plan")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.subscribe_to_plan)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "plan_version_id" in params
        assert "billing_period" in params
        assert "success_url" in params
        assert "webhook_url" in params
        assert "session" in params


class TestSubscriptionServiceCancel:
    """Tests for SubscriptionService.cancel method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "cancel")

    def test_is_async(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert inspect.iscoroutinefunction(SubscriptionService.cancel)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        attr = inspect.getattr_static(SubscriptionService, "cancel")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        sig = inspect.signature(SubscriptionService.cancel)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "session" in params
