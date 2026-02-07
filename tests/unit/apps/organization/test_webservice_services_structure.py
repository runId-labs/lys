"""
Unit tests for organization webservice services structure.

Tests class structure and method signatures of OrganizationWebserviceService.
"""

import inspect

from lys.apps.organization.modules.webservice.services import OrganizationWebserviceService
from lys.apps.user_role.modules.webservice.services import RoleWebserviceService


class TestOrganizationWebserviceServiceStructure:
    """Tests for OrganizationWebserviceService class structure."""

    def test_class_exists(self):
        assert OrganizationWebserviceService is not None

    def test_inherits_from_role_webservice_service(self):
        assert issubclass(OrganizationWebserviceService, RoleWebserviceService)

    def test_has_accessible_webservices_or_where(self):
        assert hasattr(OrganizationWebserviceService, "_accessible_webservices_or_where")

    def test_has_user_has_org_role_for_webservice(self):
        assert hasattr(OrganizationWebserviceService, "_user_has_org_role_for_webservice")

    def test_has_get_user_access_levels(self):
        assert hasattr(OrganizationWebserviceService, "get_user_access_levels")


class TestOrganizationWebserviceServiceAsyncMethods:
    """Tests for async method signatures."""

    def test_accessible_webservices_or_where_is_async(self):
        assert inspect.iscoroutinefunction(
            OrganizationWebserviceService._accessible_webservices_or_where
        )

    def test_user_has_org_role_for_webservice_is_async(self):
        assert inspect.iscoroutinefunction(
            OrganizationWebserviceService._user_has_org_role_for_webservice
        )

    def test_get_user_access_levels_is_async(self):
        assert inspect.iscoroutinefunction(
            OrganizationWebserviceService.get_user_access_levels
        )


class TestOrganizationWebserviceServiceSignatures:
    """Tests for method parameter signatures."""

    def test_accessible_webservices_or_where_params(self):
        sig = inspect.signature(
            OrganizationWebserviceService._accessible_webservices_or_where
        )
        params = list(sig.parameters.keys())
        assert "stmt" in params
        assert "user" in params

    def test_user_has_org_role_for_webservice_params(self):
        sig = inspect.signature(
            OrganizationWebserviceService._user_has_org_role_for_webservice
        )
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "webservice_id" in params
        assert "session" in params

    def test_get_user_access_levels_params(self):
        sig = inspect.signature(
            OrganizationWebserviceService.get_user_access_levels
        )
        params = list(sig.parameters.keys())
        assert "webservice" in params
        assert "user" in params
        assert "session" in params
