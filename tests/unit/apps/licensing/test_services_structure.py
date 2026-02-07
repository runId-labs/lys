"""
Unit tests for licensing service structure (method signatures, inheritance, classmethods).
"""
import inspect

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestLicenseCheckerServiceStructure:
    """Tests for LicenseCheckerService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert LicenseCheckerService is not None

    def test_inherits_from_service(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        from lys.core.services import Service
        assert issubclass(LicenseCheckerService, Service)

    def test_service_name(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert LicenseCheckerService.service_name == "license_checker"

    def test_has_check_quota_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_quota")
        assert inspect.iscoroutinefunction(LicenseCheckerService.check_quota)

    def test_has_enforce_quota_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_quota")
        assert inspect.iscoroutinefunction(LicenseCheckerService.enforce_quota)

    def test_has_check_feature_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_feature")
        assert inspect.iscoroutinefunction(LicenseCheckerService.check_feature)

    def test_has_enforce_feature_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_feature")
        assert inspect.iscoroutinefunction(LicenseCheckerService.enforce_feature)

    def test_has_get_client_limits_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "get_client_limits")
        assert inspect.iscoroutinefunction(LicenseCheckerService.get_client_limits)

    def test_has_validate_downgrade_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "validate_downgrade")
        assert inspect.iscoroutinefunction(LicenseCheckerService.validate_downgrade)

    def test_has_execute_downgrade_method(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "execute_downgrade")
        assert inspect.iscoroutinefunction(LicenseCheckerService.execute_downgrade)

    def test_has_check_subscription_from_claims(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_subscription_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.check_subscription_from_claims)

    def test_has_check_quota_from_claims(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_quota_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.check_quota_from_claims)

    def test_has_enforce_quota_from_claims(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_quota_from_claims")
        assert not inspect.iscoroutinefunction(LicenseCheckerService.enforce_quota_from_claims)

    def test_has_check_feature_from_claims(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "check_feature_from_claims")

    def test_has_enforce_feature_from_claims(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "enforce_feature_from_claims")

    def test_has_get_limits_from_claims(self):
        from lys.apps.licensing.modules.checker.services import LicenseCheckerService
        assert hasattr(LicenseCheckerService, "get_limits_from_claims")


class TestSubscriptionServiceStructure:
    """Tests for SubscriptionService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert SubscriptionService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        from lys.core.services import EntityService
        assert issubclass(SubscriptionService, EntityService)

    def test_has_get_client_subscription(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "get_client_subscription")
        assert inspect.iscoroutinefunction(SubscriptionService.get_client_subscription)

    def test_has_subscribe_to_plan(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "subscribe_to_plan")
        assert inspect.iscoroutinefunction(SubscriptionService.subscribe_to_plan)

    def test_has_cancel(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "cancel")
        assert inspect.iscoroutinefunction(SubscriptionService.cancel)

    def test_has_add_user_to_subscription(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "add_user_to_subscription")
        assert inspect.iscoroutinefunction(SubscriptionService.add_user_to_subscription)

    def test_has_remove_user_from_subscription(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "remove_user_from_subscription")
        assert inspect.iscoroutinefunction(SubscriptionService.remove_user_from_subscription)

    def test_has_is_user_licensed(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService
        assert hasattr(SubscriptionService, "is_user_licensed")
        assert inspect.iscoroutinefunction(SubscriptionService.is_user_licensed)


class TestLicensingUserServiceStructure:
    """Tests for licensing UserService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.user.services import UserService
        assert UserService is not None

    def test_inherits_from_base_user_service(self):
        from lys.apps.licensing.modules.user.services import UserService
        from lys.apps.organization.modules.user.services import UserService as BaseUserService
        assert issubclass(UserService, BaseUserService)

    def test_has_add_to_subscription(self):
        from lys.apps.licensing.modules.user.services import UserService
        assert hasattr(UserService, "add_to_subscription")
        assert inspect.iscoroutinefunction(UserService.add_to_subscription)

    def test_add_to_subscription_signature(self):
        from lys.apps.licensing.modules.user.services import UserService
        sig = inspect.signature(UserService.add_to_subscription)
        assert "user" in sig.parameters
        assert "session" in sig.parameters
        assert "background_tasks" in sig.parameters

    def test_has_remove_from_subscription(self):
        from lys.apps.licensing.modules.user.services import UserService
        assert hasattr(UserService, "remove_from_subscription")
        assert inspect.iscoroutinefunction(UserService.remove_from_subscription)

    def test_remove_from_subscription_signature(self):
        from lys.apps.licensing.modules.user.services import UserService
        sig = inspect.signature(UserService.remove_from_subscription)
        assert "user" in sig.parameters
        assert "session" in sig.parameters
        assert "background_tasks" in sig.parameters


class TestLicensingAuthServiceStructure:
    """Tests for LicensingAuthService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert LicensingAuthService is not None

    def test_inherits_from_organization_auth_service(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        from lys.apps.organization.modules.auth.services import OrganizationAuthService
        assert issubclass(LicensingAuthService, OrganizationAuthService)

    def test_has_generate_access_claims(self):
        from lys.apps.licensing.modules.auth.services import LicensingAuthService
        assert hasattr(LicensingAuthService, "generate_access_claims")
        assert inspect.iscoroutinefunction(LicensingAuthService.generate_access_claims)


class TestLicensingWebserviceServiceStructure:
    """Tests for LicensingWebserviceService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService
        assert LicensingWebserviceService is not None

    def test_inherits_from_organization_webservice_service(self):
        from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService
        from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
        assert issubclass(LicensingWebserviceService, OrganizationWebserviceService)

    def test_has_accessible_webservices_or_where(self):
        from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService
        assert hasattr(LicensingWebserviceService, "_accessible_webservices_or_where")

    def test_has_get_user_access_levels(self):
        from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService
        assert hasattr(LicensingWebserviceService, "get_user_access_levels")
        assert inspect.iscoroutinefunction(LicensingWebserviceService.get_user_access_levels)


class TestLicensingClientServiceStructure:
    """Tests for licensing ClientService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.client.services import ClientService
        assert ClientService is not None

    def test_inherits_from_base_client_service(self):
        from lys.apps.licensing.modules.client.services import ClientService
        from lys.apps.organization.modules.client.services import ClientService as BaseClientService
        assert issubclass(ClientService, BaseClientService)

    def test_has_create_client_with_owner(self):
        from lys.apps.licensing.modules.client.services import ClientService
        assert hasattr(ClientService, "create_client_with_owner")
        assert inspect.iscoroutinefunction(ClientService.create_client_with_owner)


class TestLicenseApplicationServiceStructure:
    """Tests for LicenseApplicationService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.application.services import LicenseApplicationService
        assert LicenseApplicationService is not None


class TestRuleValidatorsStructure:
    """Tests for rule validator functions."""

    def test_validate_max_users_exists(self):
        from lys.apps.licensing.modules.rule.validators import validate_max_users
        assert validate_max_users is not None
        assert inspect.iscoroutinefunction(validate_max_users)

    def test_validate_max_users_signature(self):
        from lys.apps.licensing.modules.rule.validators import validate_max_users
        sig = inspect.signature(validate_max_users)
        assert "session" in sig.parameters
        assert "client_id" in sig.parameters
        assert "app_id" in sig.parameters
        assert "limit_value" in sig.parameters

    def test_validate_max_projects_per_month_exists(self):
        from lys.apps.licensing.modules.rule.validators import validate_max_projects_per_month
        assert validate_max_projects_per_month is not None
        assert inspect.iscoroutinefunction(validate_max_projects_per_month)
