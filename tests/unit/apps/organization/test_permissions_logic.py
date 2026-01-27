"""
Unit tests for organization permissions logic with mocks.

Tests OrganizationPermission statement constraints.
Note: Tests involving SQLAlchemy or_() are tested at integration level.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestOrganizationPermissionAddStatementAccessConstraintsLogic:
    """Tests for add_statement_access_constraints method with organization key."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        return context

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_entity_class_is_none(self, mock_context):
        """Test that stmt is unchanged when entity_class is None."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY

        mock_context.access_type = {
            ORGANIZATION_ROLE_ACCESS_KEY: {"client": ["client-1"]}
        }

        mock_stmt = MagicMock()
        mock_stmt.froms = [MagicMock()]
        or_where = MagicMock()

        result_stmt, result_where = await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, None  # entity_class is None
        )

        assert result_stmt == mock_stmt

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_stmt_has_no_froms(self, mock_context):
        """Test that stmt is unchanged when it has no froms."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY

        mock_entity_class = MagicMock()

        mock_context.access_type = {
            ORGANIZATION_ROLE_ACCESS_KEY: {"client": ["client-1"]}
        }

        mock_stmt = MagicMock()
        mock_stmt.froms = []  # Empty froms

        or_where = MagicMock()

        result_stmt, result_where = await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, mock_entity_class
        )

        # organization_accessing_filters should not be called
        mock_entity_class.organization_accessing_filters.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_access_type_is_not_dict(self, mock_context):
        """Test that stmt is unchanged when access_type is not a dict."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.access_type = True  # Boolean, not dict

        mock_stmt = MagicMock()
        mock_stmt.froms = [MagicMock()]
        or_where = MagicMock()
        mock_entity_class = MagicMock()

        result_stmt, result_where = await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, mock_entity_class
        )

        # organization_accessing_filters should not be called
        mock_entity_class.organization_accessing_filters.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_no_organization_key(self, mock_context):
        """Test that stmt is unchanged when access_type has no organization key."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.access_type = {"other_key": {"data": "value"}}  # No ORGANIZATION_ROLE_ACCESS_KEY

        mock_stmt = MagicMock()
        mock_stmt.froms = [MagicMock()]
        or_where = MagicMock()
        mock_entity_class = MagicMock()

        result_stmt, result_where = await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, mock_entity_class
        )

        # organization_accessing_filters should not be called
        mock_entity_class.organization_accessing_filters.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_organization_filters_when_conditions_met(self, mock_context):
        """Test organization_accessing_filters is called when all conditions are met."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY

        mock_context.access_type = {
            ORGANIZATION_ROLE_ACCESS_KEY: {"client": ["client-1"]}
        }

        mock_stmt = MagicMock()
        mock_stmt.froms = [MagicMock()]

        mock_entity_class = MagicMock()
        # Return empty conditions to avoid SQLAlchemy or_() issue
        mock_entity_class.organization_accessing_filters.return_value = (mock_stmt, [])

        or_where = MagicMock()

        await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, mock_entity_class
        )

        # Verify organization_accessing_filters was called with correct args
        mock_entity_class.organization_accessing_filters.assert_called_once_with(
            mock_stmt, {"client": ["client-1"]}
        )


class TestOrganizationPermissionMethodSignatures:
    """Tests for OrganizationPermission method signatures."""

    def test_add_statement_access_constraints_is_async(self):
        """Test that add_statement_access_constraints is async."""
        import inspect
        from lys.apps.organization.permissions import OrganizationPermission

        assert inspect.iscoroutinefunction(OrganizationPermission.add_statement_access_constraints)

    def test_add_statement_access_constraints_signature(self):
        """Test add_statement_access_constraints method signature."""
        import inspect
        from lys.apps.organization.permissions import OrganizationPermission

        sig = inspect.signature(OrganizationPermission.add_statement_access_constraints)
        assert "stmt" in sig.parameters
        assert "or_where" in sig.parameters
        assert "context" in sig.parameters
        assert "entity_class" in sig.parameters

    def test_check_webservice_permission_is_async(self):
        """Test that check_webservice_permission is async."""
        import inspect
        from lys.apps.organization.permissions import OrganizationPermission

        assert inspect.iscoroutinefunction(OrganizationPermission.check_webservice_permission)

    def test_check_webservice_permission_signature(self):
        """Test check_webservice_permission method signature."""
        import inspect
        from lys.apps.organization.permissions import OrganizationPermission

        sig = inspect.signature(OrganizationPermission.check_webservice_permission)
        assert "webservice_id" in sig.parameters
        assert "context" in sig.parameters
