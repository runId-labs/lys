"""
Unit tests for user_role webservice module webservices.

Tests RoleWebserviceQuery GraphQL query structure.
"""

import pytest


class TestRoleWebserviceQueryStructure:
    """Tests for RoleWebserviceQuery class structure."""

    def test_role_webservice_query_exists(self):
        """Test RoleWebserviceQuery class exists."""
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery
        assert RoleWebserviceQuery is not None

    def test_role_webservice_query_inherits_from_query(self):
        """Test RoleWebserviceQuery inherits from Query."""
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery
        from lys.core.graphql.types import Query
        assert issubclass(RoleWebserviceQuery, Query)

    def test_role_webservice_query_has_all_accessible_webservices_method(self):
        """Test RoleWebserviceQuery has all_accessible_webservices method."""
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery
        assert hasattr(RoleWebserviceQuery, "all_accessible_webservices")

    def test_role_webservice_query_is_strawberry_type(self):
        """Test RoleWebserviceQuery has strawberry type definition."""
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery
        assert hasattr(RoleWebserviceQuery, "__strawberry_definition__")


class TestAllAccessibleWebservicesMethod:
    """Tests for RoleWebserviceQuery.all_accessible_webservices method."""

    def test_all_accessible_webservices_is_async(self):
        """Test all_accessible_webservices is async."""
        import inspect
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery
        assert inspect.iscoroutinefunction(RoleWebserviceQuery.all_accessible_webservices)

    def test_all_accessible_webservices_signature_has_info(self):
        """Test all_accessible_webservices signature has info parameter."""
        import inspect
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery

        sig = inspect.signature(RoleWebserviceQuery.all_accessible_webservices)
        assert "info" in sig.parameters

    def test_all_accessible_webservices_signature_has_role_code(self):
        """Test all_accessible_webservices signature has role_code parameter."""
        import inspect
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery

        sig = inspect.signature(RoleWebserviceQuery.all_accessible_webservices)
        assert "role_code" in sig.parameters

    def test_all_accessible_webservices_role_code_is_optional(self):
        """Test all_accessible_webservices role_code parameter is optional."""
        import inspect
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery

        sig = inspect.signature(RoleWebserviceQuery.all_accessible_webservices)
        assert sig.parameters["role_code"].default is None


class TestRoleWebserviceQueryRegistration:
    """Tests for RoleWebserviceQuery registration."""

    def test_role_webservice_query_registered(self):
        """Test RoleWebserviceQuery is registered."""
        from lys.apps.user_role.modules.webservice.webservices import RoleWebserviceQuery
        # The class should be importable and decorated
        assert RoleWebserviceQuery is not None
