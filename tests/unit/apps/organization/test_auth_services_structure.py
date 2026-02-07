"""
Unit tests for organization auth services structure.

Tests class structure and method signatures of OrganizationAuthService.
"""

import inspect

from lys.apps.organization.modules.auth.services import OrganizationAuthService
from lys.apps.user_role.modules.auth.services import RoleAuthService


class TestOrganizationAuthServiceStructure:
    """Tests for OrganizationAuthService class structure."""

    def test_class_exists(self):
        assert OrganizationAuthService is not None

    def test_inherits_from_role_auth_service(self):
        assert issubclass(OrganizationAuthService, RoleAuthService)

    def test_has_generate_access_claims(self):
        assert hasattr(OrganizationAuthService, "generate_access_claims")

    def test_has_get_user_organizations(self):
        assert hasattr(OrganizationAuthService, "_get_user_organizations")

    def test_has_get_owner_webservices(self):
        assert hasattr(OrganizationAuthService, "_get_owner_webservices")

    def test_has_get_client_user_role_webservices(self):
        assert hasattr(OrganizationAuthService, "_get_client_user_role_webservices")


class TestOrganizationAuthServiceAsyncMethods:
    """Tests for async method signatures."""

    def test_generate_access_claims_is_async(self):
        assert inspect.iscoroutinefunction(OrganizationAuthService.generate_access_claims)

    def test_get_user_organizations_is_async(self):
        assert inspect.iscoroutinefunction(OrganizationAuthService._get_user_organizations)

    def test_get_owner_webservices_is_async(self):
        assert inspect.iscoroutinefunction(OrganizationAuthService._get_owner_webservices)

    def test_get_client_user_role_webservices_is_async(self):
        assert inspect.iscoroutinefunction(OrganizationAuthService._get_client_user_role_webservices)


class TestOrganizationAuthServiceSignatures:
    """Tests for method parameter signatures."""

    def test_generate_access_claims_params(self):
        sig = inspect.signature(OrganizationAuthService.generate_access_claims)
        params = list(sig.parameters.keys())
        assert "user" in params
        assert "session" in params

    def test_get_user_organizations_params(self):
        sig = inspect.signature(OrganizationAuthService._get_user_organizations)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "session" in params

    def test_get_owner_webservices_params(self):
        sig = inspect.signature(OrganizationAuthService._get_owner_webservices)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "session" in params

    def test_get_client_user_role_webservices_params(self):
        sig = inspect.signature(OrganizationAuthService._get_client_user_role_webservices)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "session" in params
