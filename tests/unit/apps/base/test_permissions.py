"""
Unit tests for base app permissions.

Tests BasePermission and InternalServicePermission classes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL


class TestBasePermissionCheckWebservicePermission:
    """Tests for BasePermission.check_webservice_permission method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_always_returns_true(self, mock_context):
        """Test that BasePermission always grants access."""
        from lys.apps.base.permissions import BasePermission

        result, error = await BasePermission.check_webservice_permission(
            "any_webservice", mock_context
        )

        assert result is True
        assert error is None

    @pytest.mark.asyncio
    async def test_grants_access_to_any_webservice(self, mock_context):
        """Test that any webservice ID is granted access."""
        from lys.apps.base.permissions import BasePermission

        for ws_id in ["get_users", "create_order", "delete_admin", "unknown"]:
            result, error = await BasePermission.check_webservice_permission(
                ws_id, mock_context
            )
            assert result is True
            assert error is None


class TestBasePermissionAddStatementAccessConstraints:
    """Tests for BasePermission.add_statement_access_constraints method."""

    @pytest.mark.asyncio
    async def test_returns_unchanged_statement(self):
        """Test that statement and or_where are returned unchanged."""
        from lys.apps.base.permissions import BasePermission

        stmt = MagicMock()
        or_where = MagicMock()
        context = MagicMock()
        entity_type = MagicMock()

        result_stmt, result_where = await BasePermission.add_statement_access_constraints(
            stmt, or_where, context, entity_type
        )

        assert result_stmt is stmt
        assert result_where is or_where


class TestInternalServicePermissionCheckWebservicePermission:
    """Tests for InternalServicePermission.check_webservice_permission method."""

    @pytest.fixture
    def context_with_service_caller(self):
        """Create context with service caller."""
        context = MagicMock()
        context.service_caller = {"service_name": "auth-service"}
        context.app_manager.registry.webservices = {
            "internal_endpoint": {
                "attributes": {
                    "access_levels": [INTERNAL_SERVICE_ACCESS_LEVEL]
                }
            },
            "public_endpoint": {
                "attributes": {
                    "access_levels": ["PUBLIC"]
                }
            }
        }
        return context

    @pytest.fixture
    def context_without_service_caller(self):
        """Create context without service caller."""
        context = MagicMock()
        context.service_caller = None
        return context

    @pytest.mark.asyncio
    async def test_grants_access_to_internal_endpoint(self, context_with_service_caller):
        """Test that internal service can access internal endpoint."""
        from lys.apps.base.permissions import InternalServicePermission

        result, error = await InternalServicePermission.check_webservice_permission(
            "internal_endpoint", context_with_service_caller
        )

        assert result is True
        assert error is None

    @pytest.mark.asyncio
    async def test_defers_when_no_service_caller(self, context_without_service_caller):
        """Test that permission defers when no service caller."""
        from lys.apps.base.permissions import InternalServicePermission

        result, error = await InternalServicePermission.check_webservice_permission(
            "internal_endpoint", context_without_service_caller
        )

        assert result is None
        assert error is None

    @pytest.mark.asyncio
    async def test_defers_when_endpoint_not_internal(self, context_with_service_caller):
        """Test that permission defers when endpoint doesn't allow internal access."""
        from lys.apps.base.permissions import InternalServicePermission

        result, error = await InternalServicePermission.check_webservice_permission(
            "public_endpoint", context_with_service_caller
        )

        assert result is None
        assert error is None

    @pytest.mark.asyncio
    async def test_defers_when_endpoint_not_found(self, context_with_service_caller):
        """Test that permission defers when endpoint not in registry."""
        from lys.apps.base.permissions import InternalServicePermission

        result, error = await InternalServicePermission.check_webservice_permission(
            "unknown_endpoint", context_with_service_caller
        )

        assert result is None
        assert error is None

    @pytest.mark.asyncio
    async def test_defers_when_access_levels_empty(self, context_with_service_caller):
        """Test that permission defers when access_levels is empty."""
        from lys.apps.base.permissions import InternalServicePermission

        context_with_service_caller.app_manager.registry.webservices["empty_endpoint"] = {
            "attributes": {
                "access_levels": []
            }
        }

        result, error = await InternalServicePermission.check_webservice_permission(
            "empty_endpoint", context_with_service_caller
        )

        assert result is None
        assert error is None


class TestInternalServicePermissionAddStatementAccessConstraints:
    """Tests for InternalServicePermission.add_statement_access_constraints method."""

    @pytest.mark.asyncio
    async def test_returns_unchanged_statement(self):
        """Test that statement and or_where are returned unchanged (no row filtering)."""
        from lys.apps.base.permissions import InternalServicePermission

        stmt = MagicMock()
        or_where = MagicMock()
        context = MagicMock()
        entity_type = MagicMock()

        result_stmt, result_where = await InternalServicePermission.add_statement_access_constraints(
            stmt, or_where, context, entity_type
        )

        assert result_stmt is stmt
        assert result_where is or_where


class TestPermissionInterfaces:
    """Tests for permission interface compliance."""

    def test_base_permission_implements_interface(self):
        """Test that BasePermission implements PermissionInterface."""
        from lys.apps.base.permissions import BasePermission
        from lys.core.interfaces.permissions import PermissionInterface

        assert issubclass(BasePermission, PermissionInterface)

    def test_internal_service_permission_implements_interface(self):
        """Test that InternalServicePermission implements PermissionInterface."""
        from lys.apps.base.permissions import InternalServicePermission
        from lys.core.interfaces.permissions import PermissionInterface

        assert issubclass(InternalServicePermission, PermissionInterface)
