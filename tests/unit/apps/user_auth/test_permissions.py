"""
Unit tests for user_auth permissions.

Tests AnonymousPermission and JWTPermission classes for webservice access control.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from lys.apps.user_auth.permissions import AnonymousPermission, JWTPermission, UserAuthPermission
from lys.apps.user_auth.consts import OWNER_ACCESS_KEY
from lys.apps.user_auth.errors import ACCESS_DENIED_ERROR


class TestAnonymousPermissionCheckWebservicePermission:
    """Tests for AnonymousPermission.check_webservice_permission method."""

    @pytest.fixture
    def context_anonymous(self):
        """Create context for anonymous user (not connected)."""
        context = MagicMock()
        context.connected_user = None
        context.app_manager.registry.webservices = {}
        return context

    @pytest.fixture
    def context_connected(self):
        """Create context for connected user."""
        context = MagicMock()
        context.connected_user = {"sub": "user-123"}
        return context

    @pytest.mark.asyncio
    async def test_anonymous_user_public_webservice_granted(self, context_anonymous):
        """Test that anonymous user can access public webservice."""
        context_anonymous.app_manager.registry.webservices = {
            "get_public_data": {
                "attributes": {"public_type": "NO_LIMITATION"}
            }
        }

        result, error = await AnonymousPermission.check_webservice_permission(
            "get_public_data", context_anonymous
        )

        assert result is True
        assert error is None

    @pytest.mark.asyncio
    async def test_anonymous_user_private_webservice_denied(self, context_anonymous):
        """Test that anonymous user cannot access private webservice."""
        context_anonymous.app_manager.registry.webservices = {
            "get_private_data": {
                "attributes": {}  # No public_type
            }
        }

        result, error = await AnonymousPermission.check_webservice_permission(
            "get_private_data", context_anonymous
        )

        assert result is None
        assert error == ACCESS_DENIED_ERROR

    @pytest.mark.asyncio
    async def test_anonymous_user_unknown_webservice_denied(self, context_anonymous):
        """Test that anonymous user cannot access unknown webservice."""
        context_anonymous.app_manager.registry.webservices = {}

        result, error = await AnonymousPermission.check_webservice_permission(
            "unknown_webservice", context_anonymous
        )

        assert result is None
        assert error == ACCESS_DENIED_ERROR

    @pytest.mark.asyncio
    async def test_connected_user_defers_to_other_permissions(self, context_connected):
        """Test that connected user is deferred to other permission handlers."""
        result, error = await AnonymousPermission.check_webservice_permission(
            "any_webservice", context_connected
        )

        assert result is None
        assert error is None  # No error, just defer


class TestAnonymousPermissionAddStatementAccessConstraints:
    """Tests for AnonymousPermission.add_statement_access_constraints method."""

    @pytest.mark.asyncio
    async def test_no_constraints_added(self):
        """Test that no constraints are added for anonymous access."""
        stmt = MagicMock()
        or_where = MagicMock()
        context = MagicMock()
        entity_class = MagicMock()

        result_stmt, result_where = await AnonymousPermission.add_statement_access_constraints(
            stmt, or_where, context, entity_class
        )

        # Should return unchanged
        assert result_stmt is stmt
        assert result_where is or_where


class TestJWTPermissionCheckWebservicePermission:
    """Tests for JWTPermission.check_webservice_permission method."""

    @pytest.fixture
    def context_not_connected(self):
        """Create context for not connected user."""
        context = MagicMock()
        context.connected_user = None
        return context

    @pytest.fixture
    def context_super_user(self):
        """Create context for super user."""
        context = MagicMock()
        context.connected_user = {
            "sub": "admin-123",
            "is_super_user": True,
            "webservices": {}
        }
        return context

    @pytest.fixture
    def context_regular_user(self):
        """Create context for regular user with webservices."""
        context = MagicMock()
        context.connected_user = {
            "sub": "user-456",
            "is_super_user": False,
            "webservices": {
                "get_users": "full",
                "update_profile": "owner",
                "get_orders": "full"
            }
        }
        return context

    @pytest.mark.asyncio
    async def test_not_connected_defers(self, context_not_connected):
        """Test that not connected user is deferred."""
        result, error = await JWTPermission.check_webservice_permission(
            "any_webservice", context_not_connected
        )

        assert result is None
        assert error is None

    @pytest.mark.asyncio
    async def test_super_user_full_access(self, context_super_user):
        """Test that super user gets full access to any webservice."""
        result, error = await JWTPermission.check_webservice_permission(
            "any_webservice_even_not_in_claims", context_super_user
        )

        assert result is True
        assert error is None

    @pytest.mark.asyncio
    async def test_super_user_access_is_audit_logged(self, context_super_user, caplog):
        """Test that super user access emits an audit log entry."""
        with caplog.at_level("INFO", logger="lys.apps.user_auth.permissions"):
            await JWTPermission.check_webservice_permission(
                "sensitive_webservice", context_super_user
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "AUDIT" in record.message
        assert "admin-123" in record.message
        assert "sensitive_webservice" in record.message

    @pytest.mark.asyncio
    async def test_regular_user_full_access_granted(self, context_regular_user):
        """Test that regular user gets full access when in claims."""
        result, error = await JWTPermission.check_webservice_permission(
            "get_users", context_regular_user
        )

        assert result is True
        assert error is None

    @pytest.mark.asyncio
    async def test_regular_user_owner_access_granted(self, context_regular_user):
        """Test that regular user gets owner access when in claims."""
        result, error = await JWTPermission.check_webservice_permission(
            "update_profile", context_regular_user
        )

        assert isinstance(result, dict)
        assert result.get(OWNER_ACCESS_KEY) is True
        assert error is None

    @pytest.mark.asyncio
    async def test_regular_user_no_access_webservice_not_in_claims(self, context_regular_user):
        """Test that regular user has no access when webservice not in claims."""
        result, error = await JWTPermission.check_webservice_permission(
            "delete_users", context_regular_user  # Not in claims
        )

        assert result is None
        assert error is None  # No error, just no access from this permission

    @pytest.mark.asyncio
    async def test_user_without_webservices_claim(self):
        """Test user without webservices claim in JWT."""
        context = MagicMock()
        context.connected_user = {
            "sub": "user-789",
            "is_super_user": False
            # No "webservices" key
        }

        result, error = await JWTPermission.check_webservice_permission(
            "any_webservice", context
        )

        assert result is None
        assert error is None


class TestJWTPermissionAddStatementAccessConstraints:
    """Tests for JWTPermission.add_statement_access_constraints method."""

    @pytest.fixture
    def mock_entity_class(self):
        """Create mock entity class with user_accessing_filters."""
        entity = MagicMock()
        entity.__name__ = "MockEntity"
        entity._sensitive = False
        entity.user_accessing_filters.return_value = (MagicMock(), [MagicMock()])
        return entity

    @pytest.mark.asyncio
    async def test_owner_access_with_empty_froms_no_constraints(self, mock_entity_class):
        """Test that owner access with empty froms does not call filters.

        Note: Full constraint building with real froms requires integration tests.
        This test verifies the guard clause works correctly.
        """
        from sqlalchemy import select, literal

        # select(literal(1)) has empty get_final_froms() - guard clause should prevent filter call
        stmt = select(literal(1))
        or_where = literal(True) == literal(True)

        context = MagicMock()
        context.access_type = {OWNER_ACCESS_KEY: True}
        context.connected_user = {"sub": "user-123"}

        result_stmt, result_where = await JWTPermission.add_statement_access_constraints(
            stmt, or_where, context, mock_entity_class
        )

        # With empty get_final_froms(), user_accessing_filters should NOT be called
        mock_entity_class.user_accessing_filters.assert_not_called()
        # Statement should be returned unchanged
        assert result_stmt is stmt

    @pytest.mark.asyncio
    async def test_full_access_no_constraints(self, mock_entity_class):
        """Test that full access (True) does not add constraints."""
        stmt = MagicMock()
        stmt.froms = [MagicMock()]
        or_where = MagicMock()

        context = MagicMock()
        context.access_type = True  # Full access, not dict
        context.connected_user = {"sub": "user-123"}

        result_stmt, result_where = await JWTPermission.add_statement_access_constraints(
            stmt, or_where, context, mock_entity_class
        )

        # Should NOT have called user_accessing_filters
        mock_entity_class.user_accessing_filters.assert_not_called()
        assert result_stmt is stmt
        assert result_where is or_where

    @pytest.mark.asyncio
    async def test_no_entity_class_no_constraints(self):
        """Test that missing entity_class does not add constraints."""
        stmt = MagicMock()
        stmt.froms = [MagicMock()]
        or_where = MagicMock()

        context = MagicMock()
        context.access_type = {OWNER_ACCESS_KEY: True}
        context.connected_user = {"sub": "user-123"}

        result_stmt, result_where = await JWTPermission.add_statement_access_constraints(
            stmt, or_where, context, None  # No entity class
        )

        assert result_stmt is stmt
        assert result_where is or_where

    @pytest.mark.asyncio
    async def test_no_connected_user_no_constraints(self, mock_entity_class):
        """Test that missing connected user does not add constraints."""
        stmt = MagicMock()
        stmt.froms = [MagicMock()]
        or_where = MagicMock()

        context = MagicMock()
        context.access_type = {OWNER_ACCESS_KEY: True}
        context.connected_user = None  # Not connected

        result_stmt, result_where = await JWTPermission.add_statement_access_constraints(
            stmt, or_where, context, mock_entity_class
        )

        mock_entity_class.user_accessing_filters.assert_not_called()


class TestUserAuthPermissionAlias:
    """Tests for UserAuthPermission backward compatibility alias."""

    def test_alias_is_jwt_permission(self):
        """Test that UserAuthPermission is an alias for JWTPermission."""
        assert UserAuthPermission is JWTPermission
