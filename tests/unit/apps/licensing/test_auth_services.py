"""
Unit tests for LicensingAuthService class structure, method existence, and signatures.

Tests verify the service interface without requiring a database or external services.
"""
import inspect

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestLicensingAuthServiceClass:
    """Tests for LicensingAuthService class existence and inheritance."""

    def test_class_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert LicensingAuthService is not None

    def test_inherits_from_organization_auth_service(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        assert issubclass(LicensingAuthService, OrganizationAuthService)


class TestLicensingAuthServiceGenerateAccessClaims:
    """Tests for LicensingAuthService.generate_access_claims method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert hasattr(LicensingAuthService, "generate_access_claims")

    def test_is_async(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert inspect.iscoroutinefunction(LicensingAuthService.generate_access_claims)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        attr = inspect.getattr_static(LicensingAuthService, "generate_access_claims")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        sig = inspect.signature(LicensingAuthService.generate_access_claims)
        params = list(sig.parameters.keys())
        assert "user" in params
        assert "session" in params


class TestLicensingAuthServiceGetSubscriptionClaims:
    """Tests for LicensingAuthService._get_subscription_claims method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert hasattr(LicensingAuthService, "_get_subscription_claims")

    def test_is_async(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert inspect.iscoroutinefunction(LicensingAuthService._get_subscription_claims)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        attr = inspect.getattr_static(LicensingAuthService, "_get_subscription_claims")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        sig = inspect.signature(LicensingAuthService._get_subscription_claims)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "session" in params


class TestLicensingAuthServiceGetClientSubscriptionClaim:
    """Tests for LicensingAuthService._get_client_subscription_claim method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert hasattr(LicensingAuthService, "_get_client_subscription_claim")

    def test_is_async(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert inspect.iscoroutinefunction(LicensingAuthService._get_client_subscription_claim)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        attr = inspect.getattr_static(LicensingAuthService, "_get_client_subscription_claim")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        sig = inspect.signature(LicensingAuthService._get_client_subscription_claim)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "session" in params


class TestLicensingAuthServiceVerifySubscriptionStatus:
    """Tests for LicensingAuthService._verify_subscription_status method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert hasattr(LicensingAuthService, "_verify_subscription_status")

    def test_is_async(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert inspect.iscoroutinefunction(LicensingAuthService._verify_subscription_status)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        attr = inspect.getattr_static(LicensingAuthService, "_verify_subscription_status")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        sig = inspect.signature(LicensingAuthService._verify_subscription_status)
        params = list(sig.parameters.keys())
        assert "customer_id" in params
        assert "subscription_id" in params


class TestLicensingAuthServiceVerifyMollieSubscription:
    """Tests for LicensingAuthService._verify_mollie_subscription method."""

    def test_method_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert hasattr(LicensingAuthService, "_verify_mollie_subscription")

    def test_is_async(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert inspect.iscoroutinefunction(LicensingAuthService._verify_mollie_subscription)

    def test_is_classmethod(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        attr = inspect.getattr_static(LicensingAuthService, "_verify_mollie_subscription")
        assert isinstance(attr, classmethod)

    def test_signature(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        sig = inspect.signature(LicensingAuthService._verify_mollie_subscription)
        params = list(sig.parameters.keys())
        assert "customer_id" in params
        assert "subscription_id" in params
