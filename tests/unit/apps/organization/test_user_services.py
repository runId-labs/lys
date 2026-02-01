"""
Unit tests for organization user services.

Tests UserService and ClientUserService.
"""

import pytest
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
        import inspect

        assert hasattr(UserService, "get_user_organization_roles")
        assert inspect.iscoroutinefunction(UserService.get_user_organization_roles)


class TestUserServiceGetUserOrganizationRoles:
    """Tests for UserService.get_user_organization_roles method."""

    def test_method_signature(self):
        """Test get_user_organization_roles method signature."""
        import inspect
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.get_user_organization_roles)

        assert "user_id" in sig.parameters
        assert "session" in sig.parameters
        assert "webservice_id" in sig.parameters

    def test_webservice_id_is_optional(self):
        """Test that webservice_id parameter is optional."""
        import inspect
        from lys.apps.organization.modules.user.services import UserService

        sig = inspect.signature(UserService.get_user_organization_roles)
        param = sig.parameters["webservice_id"]

        assert param.default is None


class TestClientUserServiceStructure:
    """Tests for ClientUserService class structure."""

    def test_inherits_from_entity_service(self):
        """Test that ClientUserService inherits from EntityService."""
        from lys.apps.organization.modules.user.services import ClientUserService
        from lys.core.services import EntityService

        assert issubclass(ClientUserService, EntityService)

    def test_has_create_client_user_method(self):
        """Test that ClientUserService has create_client_user method."""
        from lys.apps.organization.modules.user.services import ClientUserService
        import inspect

        assert hasattr(ClientUserService, "create_client_user")
        assert inspect.iscoroutinefunction(ClientUserService.create_client_user)

    def test_has_update_client_user_roles_method(self):
        """Test that ClientUserService has update_client_user_roles method."""
        from lys.apps.organization.modules.user.services import ClientUserService
        import inspect

        assert hasattr(ClientUserService, "update_client_user_roles")
        assert inspect.iscoroutinefunction(ClientUserService.update_client_user_roles)


class TestClientUserServiceCreateClientUser:
    """Tests for ClientUserService.create_client_user method."""

    def test_method_signature(self):
        """Test create_client_user method signature."""
        import inspect
        from lys.apps.organization.modules.user.services import ClientUserService

        sig = inspect.signature(ClientUserService.create_client_user)

        assert "session" in sig.parameters
        assert "client_id" in sig.parameters
        assert "email" in sig.parameters
        assert "password" in sig.parameters
        assert "language_id" in sig.parameters
        assert "send_verification_email" in sig.parameters
        assert "background_tasks" in sig.parameters
        assert "first_name" in sig.parameters
        assert "last_name" in sig.parameters
        assert "gender_id" in sig.parameters
        assert "role_codes" in sig.parameters


class TestClientUserServiceUpdateClientUserRoles:
    """Tests for ClientUserService.update_client_user_roles method."""

    def test_method_signature(self):
        """Test update_client_user_roles method signature."""
        import inspect
        from lys.apps.organization.modules.user.services import ClientUserService

        sig = inspect.signature(ClientUserService.update_client_user_roles)

        assert "client_user" in sig.parameters
        assert "role_codes" in sig.parameters
        assert "session" in sig.parameters
