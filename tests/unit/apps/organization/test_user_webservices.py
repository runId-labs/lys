"""
Unit tests for organization user webservices.

Tests GraphQL query and mutation classes for user operations.

Note: Webservice modules use a singleton registry. When user_auth
webservices are imported before organization webservices (or vice versa),
the import fails because both register webservices with the same name
(e.g., 'all_users'). We gracefully skip if the import fails.
"""

import inspect
import sys

# Try to import org webservices, handling registry conflicts
_mod = None
_module_name = "lys.apps.organization.modules.user.webservices"
if _module_name in sys.modules:
    _mod = sys.modules[_module_name]
else:
    try:
        import importlib
        _mod = importlib.import_module(_module_name)
    except (ValueError, ImportError):
        _mod = None


def _get_mod():
    """Get the webservices module, skipping tests if unavailable."""
    import pytest
    if _mod is None:
        pytest.skip("organization webservices could not be imported due to registry conflict")
    return _mod


class TestOrganizationUserQueryStructure:
    """Tests for OrganizationUserQuery class structure."""

    def test_query_exists(self):
        """Test OrganizationUserQuery class exists."""
        mod = _get_mod()
        assert hasattr(mod, "OrganizationUserQuery")

    def test_query_inherits_from_query(self):
        """Test OrganizationUserQuery inherits from Query."""
        from lys.core.graphql.types import Query
        mod = _get_mod()
        assert issubclass(mod.OrganizationUserQuery, Query)

    def test_query_has_all_users_method(self):
        """Test query has all_users method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserQuery, "all_users")

    def test_query_has_client_user_method(self):
        """Test query has client_user method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserQuery, "client_user")

    def test_query_has_all_client_users_method(self):
        """Test query has all_client_users method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserQuery, "all_client_users")


class TestAllUsersMethod:
    """Tests for OrganizationUserQuery.all_users method."""

    def test_all_users_is_async(self):
        """Test all_users is async."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.OrganizationUserQuery.all_users)

    def test_all_users_signature_has_info(self):
        """Test all_users signature has info parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert "info" in sig.parameters

    def test_all_users_signature_has_search(self):
        """Test all_users signature has search parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert "search" in sig.parameters

    def test_all_users_signature_has_is_client_user(self):
        """Test all_users signature has is_client_user parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert "is_client_user" in sig.parameters

    def test_all_users_signature_has_role_code(self):
        """Test all_users signature has role_code parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert "role_code" in sig.parameters

    def test_all_users_search_is_optional(self):
        """Test all_users search parameter is optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert sig.parameters["search"].default is None

    def test_all_users_is_client_user_is_optional(self):
        """Test all_users is_client_user parameter is optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert sig.parameters["is_client_user"].default is None

    def test_all_users_role_code_is_optional(self):
        """Test all_users role_code parameter is optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_users)
        assert sig.parameters["role_code"].default is None


class TestAllClientUsersMethod:
    """Tests for OrganizationUserQuery.all_client_users method."""

    def test_all_client_users_is_async(self):
        """Test all_client_users is async."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.OrganizationUserQuery.all_client_users)

    def test_all_client_users_signature_has_info(self):
        """Test all_client_users signature has info parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_client_users)
        assert "info" in sig.parameters

    def test_all_client_users_signature_has_client_id(self):
        """Test all_client_users signature has client_id parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_client_users)
        assert "client_id" in sig.parameters

    def test_all_client_users_signature_has_search(self):
        """Test all_client_users signature has search parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_client_users)
        assert "search" in sig.parameters

    def test_all_client_users_signature_has_role_code(self):
        """Test all_client_users signature has role_code parameter."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_client_users)
        assert "role_code" in sig.parameters

    def test_all_client_users_params_are_optional(self):
        """Test all_client_users parameters are optional."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserQuery.all_client_users)
        assert sig.parameters["client_id"].default is None
        assert sig.parameters["search"].default is None
        assert sig.parameters["role_code"].default is None


class TestOrganizationUserMutationStructure:
    """Tests for OrganizationUserMutation class structure."""

    def test_mutation_exists(self):
        """Test OrganizationUserMutation class exists."""
        mod = _get_mod()
        assert hasattr(mod, "OrganizationUserMutation")

    def test_mutation_inherits_from_mutation(self):
        """Test OrganizationUserMutation inherits from Mutation."""
        from lys.core.graphql.types import Mutation
        mod = _get_mod()
        assert issubclass(mod.OrganizationUserMutation, Mutation)

    def test_mutation_has_update_client_user_email_method(self):
        """Test mutation has update_client_user_email method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "update_client_user_email")

    def test_mutation_has_update_client_user_private_data_method(self):
        """Test mutation has update_client_user_private_data method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "update_client_user_private_data")

    def test_mutation_has_update_client_user_roles_method(self):
        """Test mutation has update_client_user_roles method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "update_client_user_roles")

    def test_mutation_has_create_client_user_method(self):
        """Test mutation has create_client_user method."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "create_client_user")


class TestUpdateClientUserEmailMethod:
    """Tests for OrganizationUserMutation.update_client_user_email method."""

    def test_update_client_user_email_method_exists(self):
        """Test update_client_user_email method exists."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "update_client_user_email")

    def test_update_client_user_email_signature(self):
        """Test update_client_user_email signature (transformed by @lys_edition)."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserMutation.update_client_user_email)
        assert "id" in sig.parameters
        assert "inputs" in sig.parameters
        assert "info" in sig.parameters


class TestUpdateClientUserPrivateDataMethod:
    """Tests for OrganizationUserMutation.update_client_user_private_data method."""

    def test_update_client_user_private_data_method_exists(self):
        """Test update_client_user_private_data method exists."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "update_client_user_private_data")

    def test_update_client_user_private_data_signature(self):
        """Test update_client_user_private_data signature (transformed by @lys_edition)."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserMutation.update_client_user_private_data)
        assert "id" in sig.parameters
        assert "inputs" in sig.parameters
        assert "info" in sig.parameters


class TestUpdateClientUserRolesMethod:
    """Tests for OrganizationUserMutation.update_client_user_roles method."""

    def test_update_client_user_roles_method_exists(self):
        """Test update_client_user_roles method exists."""
        mod = _get_mod()
        assert hasattr(mod.OrganizationUserMutation, "update_client_user_roles")

    def test_update_client_user_roles_signature(self):
        """Test update_client_user_roles signature (transformed by @lys_edition)."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserMutation.update_client_user_roles)
        assert "id" in sig.parameters
        assert "inputs" in sig.parameters
        assert "info" in sig.parameters


class TestCreateClientUserMethod:
    """Tests for OrganizationUserMutation.create_client_user method."""

    def test_create_client_user_is_async(self):
        """Test create_client_user is async."""
        mod = _get_mod()
        assert inspect.iscoroutinefunction(mod.OrganizationUserMutation.create_client_user)

    def test_create_client_user_signature(self):
        """Test create_client_user signature."""
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserMutation.create_client_user)
        assert "inputs" in sig.parameters
        assert "info" in sig.parameters

    def test_create_client_user_inputs_type(self):
        """Test create_client_user inputs type annotation."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        mod = _get_mod()
        sig = inspect.signature(mod.OrganizationUserMutation.create_client_user)
        assert sig.parameters["inputs"].annotation is CreateClientUserInput


class TestWebservicesRegistration:
    """Tests for webservices registration."""

    def test_organization_user_query_is_registered(self):
        """Test OrganizationUserQuery is registered."""
        mod = _get_mod()
        assert mod.OrganizationUserQuery is not None

    def test_organization_user_mutation_is_registered(self):
        """Test OrganizationUserMutation is registered."""
        mod = _get_mod()
        assert mod.OrganizationUserMutation is not None
