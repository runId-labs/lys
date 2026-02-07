"""
Unit tests for licensing webservice services.

Tests structure and method signatures of LicensingWebserviceService.
"""

import inspect

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService
from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService


class TestLicensingWebserviceServiceStructure:
    """Tests for LicensingWebserviceService class structure."""

    def test_class_exists(self):
        assert LicensingWebserviceService is not None

    def test_inherits_from_organization_webservice_service(self):
        assert issubclass(LicensingWebserviceService, OrganizationWebserviceService)

    def test_has_accessible_webservices_or_where(self):
        assert hasattr(LicensingWebserviceService, "_accessible_webservices_or_where")

    def test_has_user_has_org_role_with_license(self):
        assert hasattr(LicensingWebserviceService, "_user_has_org_role_for_webservice_with_license")

    def test_has_owner_client_has_subscription(self):
        assert hasattr(LicensingWebserviceService, "_owner_client_has_subscription")

    def test_has_get_user_access_levels(self):
        assert hasattr(LicensingWebserviceService, "get_user_access_levels")


class TestLicensingWebserviceServiceAsyncMethods:
    """Tests for async method signatures."""

    def test_accessible_webservices_or_where_is_async(self):
        assert inspect.iscoroutinefunction(
            LicensingWebserviceService._accessible_webservices_or_where
        )

    def test_user_has_org_role_with_license_is_async(self):
        assert inspect.iscoroutinefunction(
            LicensingWebserviceService._user_has_org_role_for_webservice_with_license
        )

    def test_owner_client_has_subscription_is_async(self):
        assert inspect.iscoroutinefunction(
            LicensingWebserviceService._owner_client_has_subscription
        )

    def test_get_user_access_levels_is_async(self):
        assert inspect.iscoroutinefunction(
            LicensingWebserviceService.get_user_access_levels
        )


class TestLicensingWebserviceServiceSignatures:
    """Tests for method signatures."""

    def test_accessible_webservices_or_where_params(self):
        sig = inspect.signature(LicensingWebserviceService._accessible_webservices_or_where)
        params = list(sig.parameters.keys())
        assert "stmt" in params
        assert "user" in params

    def test_user_has_org_role_with_license_params(self):
        sig = inspect.signature(
            LicensingWebserviceService._user_has_org_role_for_webservice_with_license
        )
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "webservice_id" in params
        assert "session" in params

    def test_owner_client_has_subscription_params(self):
        sig = inspect.signature(LicensingWebserviceService._owner_client_has_subscription)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "session" in params

    def test_get_user_access_levels_params(self):
        sig = inspect.signature(LicensingWebserviceService.get_user_access_levels)
        params = list(sig.parameters.keys())
        assert "webservice" in params
        assert "user" in params
        assert "session" in params
