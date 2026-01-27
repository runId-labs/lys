"""
Unit tests for user_role role module webservices.

Tests RoleQuery GraphQL query structure.
"""

import pytest


class TestRoleQueryStructure:
    """Tests for RoleQuery class structure."""

    def test_role_query_exists(self):
        """Test RoleQuery class exists."""
        from lys.apps.user_role.modules.role.webservices import RoleQuery
        assert RoleQuery is not None

    def test_role_query_inherits_from_query(self):
        """Test RoleQuery inherits from Query."""
        from lys.apps.user_role.modules.role.webservices import RoleQuery
        from lys.core.graphql.types import Query
        assert issubclass(RoleQuery, Query)

    def test_role_query_has_all_roles_method(self):
        """Test RoleQuery has all_roles method."""
        from lys.apps.user_role.modules.role.webservices import RoleQuery
        assert hasattr(RoleQuery, "all_roles")


class TestAllRolesMethod:
    """Tests for RoleQuery.all_roles method."""

    def test_all_roles_is_async(self):
        """Test all_roles is async."""
        import inspect
        from lys.apps.user_role.modules.role.webservices import RoleQuery
        assert inspect.iscoroutinefunction(RoleQuery.all_roles)

    def test_all_roles_signature_has_info(self):
        """Test all_roles signature has info parameter."""
        import inspect
        from lys.apps.user_role.modules.role.webservices import RoleQuery

        sig = inspect.signature(RoleQuery.all_roles)
        assert "info" in sig.parameters

    def test_all_roles_signature_has_enabled(self):
        """Test all_roles signature has enabled parameter."""
        import inspect
        from lys.apps.user_role.modules.role.webservices import RoleQuery

        sig = inspect.signature(RoleQuery.all_roles)
        assert "enabled" in sig.parameters

    def test_all_roles_enabled_is_optional(self):
        """Test all_roles enabled parameter is optional."""
        import inspect
        from lys.apps.user_role.modules.role.webservices import RoleQuery

        sig = inspect.signature(RoleQuery.all_roles)
        assert sig.parameters["enabled"].default is None


class TestRoleQueryRegistration:
    """Tests for RoleQuery registration."""

    def test_role_query_is_strawberry_type(self):
        """Test RoleQuery has strawberry type definition."""
        from lys.apps.user_role.modules.role.webservices import RoleQuery
        assert hasattr(RoleQuery, "__strawberry_definition__")
