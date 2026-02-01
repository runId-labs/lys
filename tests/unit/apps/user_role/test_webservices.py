"""
Unit tests for user_role GraphQL webservices.

Tests webservice structure and configuration.

Note: The user.webservices module cannot be imported in unit tests because
it calls override_webservice() at module load time, which requires other
webservices to be registered first. These webservices are tested via integration tests.
"""

import pytest


class TestWebserviceOverrides:
    """Tests for webservice override configurations."""

    def test_override_webservice_import(self):
        """Test that override_webservice is available."""
        from lys.core.registries import override_webservice

        assert override_webservice is not None

    def test_role_access_level_constant_exists(self):
        """Test that ROLE_ACCESS_LEVEL is available for overrides."""
        from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL

        assert ROLE_ACCESS_LEVEL == "ROLE"

    def test_owner_access_level_constant_exists(self):
        """Test that OWNER_ACCESS_LEVEL is available for overrides."""
        from lys.core.consts.webservices import OWNER_ACCESS_LEVEL

        assert OWNER_ACCESS_LEVEL == "OWNER"


class TestUserServiceStructure:
    """Tests for UserService which is used by webservices."""

    def test_user_service_has_create_user(self):
        """Test that UserService has create_user method."""
        from lys.apps.user_role.modules.user.services import UserService

        assert hasattr(UserService, "create_user")

    def test_user_service_has_update_user_roles(self):
        """Test that UserService has update_user_roles method."""
        from lys.apps.user_role.modules.user.services import UserService

        assert hasattr(UserService, "update_user_roles")

    def test_user_service_create_user_is_async(self):
        """Test that create_user is async."""
        import inspect
        from lys.apps.user_role.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService.create_user)

    def test_user_service_update_user_roles_is_async(self):
        """Test that update_user_roles is async."""
        import inspect
        from lys.apps.user_role.modules.user.services import UserService

        assert inspect.iscoroutinefunction(UserService.update_user_roles)


class TestUserModelsForWebservices:
    """Tests for input models used by webservices."""

    def test_create_user_with_roles_input_model_exists(self):
        """Test that CreateUserWithRolesInputModel exists."""
        from lys.apps.user_role.modules.user.models import CreateUserWithRolesInputModel

        assert CreateUserWithRolesInputModel is not None

    def test_update_user_roles_input_model_exists(self):
        """Test that UpdateUserRolesInputModel exists."""
        from lys.apps.user_role.modules.user.models import UpdateUserRolesInputModel

        assert UpdateUserRolesInputModel is not None
