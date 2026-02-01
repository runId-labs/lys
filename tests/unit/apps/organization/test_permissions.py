"""
Unit tests for organization permission system.

Tests OrganizationPermission class.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestOrganizationPermissionCheckWebservicePermission:
    """Tests for OrganizationPermission.check_webservice_permission method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.connected_user = None
        return context

    @pytest.mark.asyncio
    async def test_returns_none_for_anonymous_user(self, mock_context):
        """Test that anonymous users get None access."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.connected_user = None

        access_type, error_code = await OrganizationPermission.check_webservice_permission(
            "test_webservice", mock_context
        )

        assert access_type is None
        assert error_code is None

    @pytest.mark.asyncio
    async def test_returns_none_for_user_without_organizations(self, mock_context):
        """Test that users without organizations get None access."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.connected_user = {"sub": "user-123", "organizations": {}}

        access_type, error_code = await OrganizationPermission.check_webservice_permission(
            "test_webservice", mock_context
        )

        assert access_type is None
        assert error_code is None

    @pytest.mark.asyncio
    async def test_returns_none_when_webservice_not_in_orgs(self, mock_context):
        """Test that users without webservice access get None."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.connected_user = {
            "sub": "user-123",
            "organizations": {
                "client-1": {
                    "level": "client",
                    "webservices": ["other_webservice"]
                }
            }
        }

        access_type, error_code = await OrganizationPermission.check_webservice_permission(
            "test_webservice", mock_context
        )

        assert access_type is None
        assert error_code is None

    @pytest.mark.asyncio
    async def test_returns_access_when_webservice_in_org(self, mock_context):
        """Test that users with webservice in org get access."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY

        mock_context.connected_user = {
            "sub": "user-123",
            "organizations": {
                "client-1": {
                    "level": "client",
                    "webservices": ["test_webservice"]
                }
            }
        }

        access_type, error_code = await OrganizationPermission.check_webservice_permission(
            "test_webservice", mock_context
        )

        assert access_type is not None
        assert ORGANIZATION_ROLE_ACCESS_KEY in access_type
        assert "client" in access_type[ORGANIZATION_ROLE_ACCESS_KEY]
        assert "client-1" in access_type[ORGANIZATION_ROLE_ACCESS_KEY]["client"]
        assert error_code is None

    @pytest.mark.asyncio
    async def test_returns_multiple_orgs_when_multiple_match(self, mock_context):
        """Test that multiple matching orgs are returned."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY

        mock_context.connected_user = {
            "sub": "user-123",
            "organizations": {
                "client-1": {
                    "level": "client",
                    "webservices": ["test_webservice"]
                },
                "client-2": {
                    "level": "client",
                    "webservices": ["test_webservice", "other"]
                }
            }
        }

        access_type, error_code = await OrganizationPermission.check_webservice_permission(
            "test_webservice", mock_context
        )

        assert access_type is not None
        assert ORGANIZATION_ROLE_ACCESS_KEY in access_type
        client_orgs = access_type[ORGANIZATION_ROLE_ACCESS_KEY]["client"]
        assert "client-1" in client_orgs
        assert "client-2" in client_orgs

    @pytest.mark.asyncio
    async def test_uses_default_level_when_not_specified(self, mock_context):
        """Test that default level 'client' is used when not specified."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY

        mock_context.connected_user = {
            "sub": "user-123",
            "organizations": {
                "org-1": {
                    "webservices": ["test_webservice"]
                }
            }
        }

        access_type, error_code = await OrganizationPermission.check_webservice_permission(
            "test_webservice", mock_context
        )

        assert access_type is not None
        assert "client" in access_type[ORGANIZATION_ROLE_ACCESS_KEY]


class TestOrganizationPermissionAddStatementAccessConstraints:
    """Tests for OrganizationPermission.add_statement_access_constraints method."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.access_type = None
        return context

    @pytest.fixture
    def mock_stmt(self):
        """Create mock SQLAlchemy statement."""
        stmt = MagicMock()
        stmt.get_final_froms.return_value = [MagicMock()]
        return stmt

    @pytest.fixture
    def mock_entity_class(self):
        """Create mock entity class."""
        entity = MagicMock()
        entity.organization_accessing_filters = MagicMock(return_value=(MagicMock(), []))
        return entity

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_access_type_not_dict(
        self, mock_context, mock_stmt, mock_entity_class
    ):
        """Test that stmt is unchanged when access_type is not dict."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.access_type = True  # Not a dict
        or_where = MagicMock()

        result_stmt, result_where = await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, mock_entity_class
        )

        assert result_stmt == mock_stmt
        assert result_where == or_where

    @pytest.mark.asyncio
    async def test_returns_unchanged_when_no_organization_key(
        self, mock_context, mock_stmt, mock_entity_class
    ):
        """Test that stmt is unchanged when no organization key in access_type."""
        from lys.apps.organization.permissions import OrganizationPermission

        mock_context.access_type = {"other_key": "value"}
        or_where = MagicMock()

        result_stmt, result_where = await OrganizationPermission.add_statement_access_constraints(
            mock_stmt, or_where, mock_context, mock_entity_class
        )

        assert result_stmt == mock_stmt


class TestOrganizationPermissionStructure:
    """Tests for OrganizationPermission class structure."""

    def test_implements_permission_interface(self):
        """Test that OrganizationPermission implements PermissionInterface."""
        from lys.apps.organization.permissions import OrganizationPermission
        from lys.core.interfaces.permissions import PermissionInterface

        assert issubclass(OrganizationPermission, PermissionInterface)

    def test_has_check_webservice_permission_method(self):
        """Test that class has check_webservice_permission method."""
        from lys.apps.organization.permissions import OrganizationPermission
        import inspect

        assert hasattr(OrganizationPermission, "check_webservice_permission")
        assert inspect.iscoroutinefunction(OrganizationPermission.check_webservice_permission)

    def test_has_add_statement_access_constraints_method(self):
        """Test that class has add_statement_access_constraints method."""
        from lys.apps.organization.permissions import OrganizationPermission
        import inspect

        assert hasattr(OrganizationPermission, "add_statement_access_constraints")
        assert inspect.iscoroutinefunction(OrganizationPermission.add_statement_access_constraints)
