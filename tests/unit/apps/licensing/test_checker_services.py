"""
Unit tests for LicenseCheckerService class structure, method existence, and signatures.

Tests verify the service interface without requiring a database or external services.
"""
import inspect

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestLicenseCheckerServiceClass:
    """Tests for LicenseCheckerService class existence and inheritance."""

    def test_class_exists(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert LicenseCheckerService is not None

    def test_inherits_from_service(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.services import Service
        assert issubclass(LicenseCheckerService, Service)

    def test_service_name_is_license_checker(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert LicenseCheckerService.service_name == "license_checker"


class TestLicenseCheckerServiceAsyncDatabaseMethods:
    """Tests for async database-based checking methods on LicenseCheckerService."""

    def test_check_quota_exists_and_is_async(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_quota")
        assert inspect.iscoroutinefunction(LicenseCheckerService.check_quota)

    def test_check_quota_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.check_quota)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "rule_id" in params
        assert "session" in params

    def test_enforce_quota_exists_and_is_async(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_quota")
        assert inspect.iscoroutinefunction(LicenseCheckerService.enforce_quota)

    def test_enforce_quota_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.enforce_quota)
        params = sig.parameters
        assert "client_id" in params
        assert "rule_id" in params
        assert "session" in params
        assert "error" in params
        assert params["error"].default is None

    def test_check_feature_exists_and_is_async(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_feature")
        assert inspect.iscoroutinefunction(LicenseCheckerService.check_feature)

    def test_check_feature_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.check_feature)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "rule_id" in params
        assert "session" in params

    def test_enforce_feature_exists_and_is_async(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_feature")
        assert inspect.iscoroutinefunction(LicenseCheckerService.enforce_feature)

    def test_enforce_feature_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.enforce_feature)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "rule_id" in params
        assert "session" in params

    def test_get_client_limits_exists_and_is_async(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "get_client_limits")
        assert inspect.iscoroutinefunction(LicenseCheckerService.get_client_limits)

    def test_get_client_limits_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.get_client_limits)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "session" in params

    def test_validate_downgrade_exists_and_is_async(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "validate_downgrade")
        assert inspect.iscoroutinefunction(LicenseCheckerService.validate_downgrade)

    def test_validate_downgrade_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.validate_downgrade)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "new_plan_version_id" in params
        assert "session" in params

    def test_execute_downgrade_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "execute_downgrade")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.execute_downgrade)

    def test_execute_downgrade_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.execute_downgrade)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "new_plan_version_id" in params
        assert "session" in params


class TestLicenseCheckerServiceSyncClaimsMethods:
    """Tests for synchronous JWT claims-based checking methods on LicenseCheckerService."""

    def test_check_subscription_from_claims_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_subscription_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.check_subscription_from_claims)

    def test_check_subscription_from_claims_is_classmethod(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        attr = inspect.getattr_static(LicenseCheckerService, "check_subscription_from_claims")
        assert isinstance(attr, classmethod)

    def test_check_subscription_from_claims_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.check_subscription_from_claims)
        params = list(sig.parameters.keys())
        assert "claims" in params
        assert "client_id" in params

    def test_check_quota_from_claims_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_quota_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.check_quota_from_claims)

    def test_check_quota_from_claims_is_classmethod(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        attr = inspect.getattr_static(LicenseCheckerService, "check_quota_from_claims")
        assert isinstance(attr, classmethod)

    def test_check_quota_from_claims_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.check_quota_from_claims)
        params = list(sig.parameters.keys())
        assert "claims" in params
        assert "client_id" in params
        assert "rule_id" in params
        assert "current_count" in params

    def test_enforce_quota_from_claims_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_quota_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.enforce_quota_from_claims)

    def test_enforce_quota_from_claims_is_classmethod(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        attr = inspect.getattr_static(LicenseCheckerService, "enforce_quota_from_claims")
        assert isinstance(attr, classmethod)

    def test_enforce_quota_from_claims_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.enforce_quota_from_claims)
        params = sig.parameters
        assert "claims" in params
        assert "client_id" in params
        assert "rule_id" in params
        assert "current_count" in params
        assert "error" in params
        assert params["error"].default is None

    def test_check_feature_from_claims_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_feature_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.check_feature_from_claims)

    def test_check_feature_from_claims_is_classmethod(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        attr = inspect.getattr_static(LicenseCheckerService, "check_feature_from_claims")
        assert isinstance(attr, classmethod)

    def test_check_feature_from_claims_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.check_feature_from_claims)
        params = list(sig.parameters.keys())
        assert "claims" in params
        assert "client_id" in params
        assert "rule_id" in params

    def test_enforce_feature_from_claims_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_feature_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.enforce_feature_from_claims)

    def test_enforce_feature_from_claims_is_classmethod(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        attr = inspect.getattr_static(LicenseCheckerService, "enforce_feature_from_claims")
        assert isinstance(attr, classmethod)

    def test_enforce_feature_from_claims_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.enforce_feature_from_claims)
        params = list(sig.parameters.keys())
        assert "claims" in params
        assert "client_id" in params
        assert "rule_id" in params

    def test_get_limits_from_claims_exists_and_is_sync(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "get_limits_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.get_limits_from_claims)

    def test_get_limits_from_claims_is_classmethod(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        attr = inspect.getattr_static(LicenseCheckerService, "get_limits_from_claims")
        assert isinstance(attr, classmethod)

    def test_get_limits_from_claims_signature(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        sig = inspect.signature(LicenseCheckerService.get_limits_from_claims)
        params = list(sig.parameters.keys())
        assert "claims" in params
        assert "client_id" in params
