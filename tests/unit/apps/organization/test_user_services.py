"""
Unit tests for organization user services.

Tests UserService structure and methods.
"""

import pytest
import inspect
from unittest.mock import MagicMock, AsyncMock, patch


class TestUserServiceStructure:
    """Tests for UserService class structure."""

    def test_inherits_from_user_role_service(self):
        """Test that UserService inherits from UserRoleService."""
        from lys.apps.organization.modules.user.services import UserService
        from lys.apps.user_role.modules.user.services import UserService as UserRoleService

        assert issubclass(UserService, UserRoleService)

    def test_has_get_user_organization_roles_method(self):
        """Test that UserService has get_user_organization_roles method."""
        from lys.apps.organization.modules.user.services import UserService

        assert hasattr(UserService, "get_user_organization_roles")
        assert inspect.iscoroutinefunction(UserService.get_user_organization_roles)

    def test_has_create_client_user_method(self):
        """Test that UserService has create_client_user method."""
        from lys.apps.organization.modules.user.services import UserService

        assert hasattr(UserService, "create_client_user")
        assert inspect.iscoroutinefunction(UserService.create_client_user)

    def test_has_update_client_user_roles_method(self):
        """Test that UserService has update_client_user_roles method."""
        from lys.apps.organization.modules.user.services import UserService

        assert hasattr(UserService, "update_client_user_roles")
        assert inspect.iscoroutinefunction(UserService.update_client_user_roles)


class TestUserServiceGetUserOrganizationRoles:
    """Tests for UserService.get_user_organization_roles method."""

    def test_method_signature(self):
        """Test get_user_organization_roles method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.get_user_organization_roles)

        assert "user_id" in sig.parameters
        assert "session" in sig.parameters
        assert "webservice_id" in sig.parameters

    def test_webservice_id_is_optional(self):
        """Test that webservice_id parameter is optional."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.get_user_organization_roles)
        param = sig.parameters["webservice_id"]

        assert param.default is None


class TestUserServiceCreateClientUser:
    """Tests for UserService.create_client_user method."""

    def test_method_signature(self):
        """Test create_client_user method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.create_client_user)

        assert "session" in sig.parameters
        assert "client_id" in sig.parameters
        assert "email" in sig.parameters
        assert "password" in sig.parameters
        assert "language_id" in sig.parameters
        assert "inviter" in sig.parameters
        assert "background_tasks" in sig.parameters
        assert "first_name" in sig.parameters
        assert "last_name" in sig.parameters
        assert "gender_id" in sig.parameters
        assert "role_codes" in sig.parameters

    def test_inviter_default_none(self):
        """Test that inviter defaults to None."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.create_client_user)
        assert sig.parameters["inviter"].default is None

    def test_optional_parameters_default_none(self):
        """Test that optional parameters default to None."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.create_client_user)
        assert sig.parameters["background_tasks"].default is None
        assert sig.parameters["first_name"].default is None
        assert sig.parameters["last_name"].default is None
        assert sig.parameters["gender_id"].default is None
        assert sig.parameters["role_codes"].default is None


class TestUserServiceUpdateClientUserRoles:
    """Tests for UserService.update_client_user_roles method."""

    def test_method_signature(self):
        """Test update_client_user_roles method signature."""
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.update_client_user_roles)

        assert "user" in sig.parameters
        assert "role_codes" in sig.parameters
        assert "session" in sig.parameters

    def test_is_classmethod(self):
        """Test that update_client_user_roles is a classmethod."""
        from lys.apps.organization.modules.user.services import UserService

        assert isinstance(
            inspect.getattr_static(UserService, "update_client_user_roles"),
            classmethod
        )
