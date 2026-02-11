"""
Unit tests for OrganizationRecipientResolutionMixin.

Tests organization-scoped recipient resolution:
- validate_organization_data
- Fallback to parent when no org_data
- Organization-scoped resolution with client_ids
- _build_organization_filters dynamic filter generation
"""
import inspect
from unittest.mock import Mock, MagicMock, patch

import pytest
from pydantic import ValidationError

from lys.apps.organization.mixins.recipient_resolution import (
    OrganizationRecipientResolutionMixin,
    OrganizationData,
)
from lys.apps.user_role.mixins.recipient_resolution import RoleRecipientResolutionMixin


class TestOrganizationRecipientResolutionMixinStructure:
    """Verify class structure and inheritance."""

    def test_class_exists(self):
        assert inspect.isclass(OrganizationRecipientResolutionMixin)

    def test_inherits_from_role_mixin(self):
        assert issubclass(OrganizationRecipientResolutionMixin, RoleRecipientResolutionMixin)

    def test_has_resolve_recipients(self):
        assert hasattr(OrganizationRecipientResolutionMixin, "_resolve_recipients")

    def test_has_resolve_recipients_sync(self):
        assert hasattr(OrganizationRecipientResolutionMixin, "_resolve_recipients_sync")

    def test_has_validate_organization_data(self):
        assert hasattr(OrganizationRecipientResolutionMixin, "validate_organization_data")

    def test_has_resolve_organization_recipients(self):
        assert hasattr(OrganizationRecipientResolutionMixin, "_resolve_organization_recipients")

    def test_has_resolve_organization_recipients_sync(self):
        assert hasattr(OrganizationRecipientResolutionMixin, "_resolve_organization_recipients_sync")

    def test_has_build_organization_filters(self):
        assert hasattr(OrganizationRecipientResolutionMixin, "_build_organization_filters")


class TestOrganizationData:
    """Tests for OrganizationData Pydantic model."""

    def test_valid_client_ids(self):
        data = OrganizationData(client_ids=["c1", "c2"])
        assert data.client_ids == ["c1", "c2"]

    def test_none_client_ids(self):
        data = OrganizationData(client_ids=None)
        assert data.client_ids is None

    def test_default_none(self):
        data = OrganizationData()
        assert data.client_ids is None

    def test_from_dict(self):
        data = OrganizationData(**{"client_ids": ["c1"]})
        assert data.client_ids == ["c1"]


class TestValidateOrganizationData:
    """Tests for validate_organization_data class method."""

    def test_none_returns_none(self):
        result = OrganizationRecipientResolutionMixin.validate_organization_data(None)
        assert result is None

    def test_valid_dict(self):
        result = OrganizationRecipientResolutionMixin.validate_organization_data(
            {"client_ids": ["c1"]}
        )
        assert isinstance(result, OrganizationData)
        assert result.client_ids == ["c1"]

    def test_empty_dict(self):
        result = OrganizationRecipientResolutionMixin.validate_organization_data({})
        assert isinstance(result, OrganizationData)
        assert result.client_ids is None


class TestBuildOrganizationFilters:
    """Tests for _build_organization_filters."""

    def test_client_ids_filter_on_user_entity(self):
        org_data = OrganizationData(client_ids=["c1", "c2"])

        client_user_role = MagicMock()
        client_user_role.client_id = None  # doesn't have it

        user_entity = MagicMock()
        user_entity.client_id = MagicMock()
        mock_in = MagicMock()
        user_entity.client_id.in_ = Mock(return_value=mock_in)

        # hasattr checks
        del client_user_role.client_id

        filters = OrganizationRecipientResolutionMixin._build_organization_filters(
            org_data, client_user_role, user_entity
        )
        assert len(filters) == 1
        user_entity.client_id.in_.assert_called_once_with(["c1", "c2"])

    def test_empty_client_ids_returns_no_filters(self):
        org_data = OrganizationData(client_ids=[])

        filters = OrganizationRecipientResolutionMixin._build_organization_filters(
            org_data, MagicMock(), MagicMock()
        )
        assert filters == []

    def test_none_client_ids_returns_no_filters(self):
        org_data = OrganizationData(client_ids=None)

        filters = OrganizationRecipientResolutionMixin._build_organization_filters(
            org_data, MagicMock(), MagicMock()
        )
        assert filters == []


class TestOrganizationRecipientResolutionSync:
    """Tests for sync _resolve_recipients_sync with org scoping."""

    def _make_type_entity(self, role_ids):
        roles = []
        for rid in role_ids:
            role = Mock()
            role.id = rid
            roles.append(role)
        entity = Mock()
        entity.roles = roles
        return entity

    def test_no_org_data_falls_back_to_parent(self):
        """Without organization_data, falls back to role-based resolution."""
        type_entity = self._make_type_entity([])

        result = OrganizationRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=Mock(),
            session=Mock(),
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
            organization_data=None,
        )
        assert set(result) == {"user-1"}

    def test_with_org_data_includes_triggered_by(self):
        """With org_data, triggered_by user is still included."""
        type_entity = self._make_type_entity([])
        org_data = OrganizationData(client_ids=["c1"])

        app_manager = Mock()
        app_manager.get_entity.return_value = None  # no client_user_role entity

        result = OrganizationRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=app_manager,
            session=Mock(),
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
            organization_data=org_data,
        )
        assert set(result) == {"user-1"}

    @patch("lys.apps.organization.mixins.recipient_resolution.select")
    def test_with_org_data_and_roles_queries_client_user_role(self, mock_select):
        """With org_data and roles, queries client_user_role table."""
        type_entity = self._make_type_entity(["ADMIN_ROLE"])
        org_data = OrganizationData(client_ids=["c1"])

        client_user_role_entity = MagicMock()
        user_entity = MagicMock()
        user_entity.client_id = MagicMock()
        user_entity.client_id.in_ = Mock(return_value="client_filter")

        app_manager = Mock()

        def get_entity_side_effect(name, nullable=False):
            if name == "client_user_role":
                return client_user_role_entity
            if name == "user":
                return user_entity
            return None

        app_manager.get_entity.side_effect = get_entity_side_effect

        # Mock select chain
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.select_from.return_value = mock_stmt
        mock_stmt.join.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        session = Mock()
        session.execute.return_value = [("user-2",), ("user-3",)]

        result = OrganizationRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=app_manager,
            session=session,
            type_entity=type_entity,
            triggered_by_user_id=None,
            additional_user_ids=None,
            organization_data=org_data,
        )
        assert set(result) == {"user-2", "user-3"}
