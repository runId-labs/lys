"""
Unit tests for RoleRecipientResolutionMixin (user_role).

Tests role-based recipient resolution:
- Roles present on type_entity
- No roles on type_entity
- Empty roles list
- Sync and async variants
"""
import inspect
from unittest.mock import Mock, AsyncMock, MagicMock, patch

import pytest

from lys.apps.base.mixins.recipient_resolution import RecipientResolutionMixin
from lys.apps.user_role.mixins.recipient_resolution import RoleRecipientResolutionMixin


class TestRoleRecipientResolutionMixinStructure:
    """Verify class structure and inheritance."""

    def test_class_exists(self):
        assert inspect.isclass(RoleRecipientResolutionMixin)

    def test_inherits_from_base_mixin(self):
        assert issubclass(RoleRecipientResolutionMixin, RecipientResolutionMixin)

    def test_has_resolve_recipients(self):
        assert hasattr(RoleRecipientResolutionMixin, "_resolve_recipients")

    def test_resolve_recipients_is_async(self):
        assert inspect.iscoroutinefunction(RoleRecipientResolutionMixin._resolve_recipients)

    def test_has_resolve_recipients_sync(self):
        assert hasattr(RoleRecipientResolutionMixin, "_resolve_recipients_sync")

    def test_resolve_recipients_sync_is_sync(self):
        assert not inspect.iscoroutinefunction(
            RoleRecipientResolutionMixin._resolve_recipients_sync
        )


class TestRoleRecipientResolutionMixinSync:
    """Tests for sync _resolve_recipients_sync with role-based resolution."""

    def _make_type_entity(self, role_ids):
        """Create a mock type entity with roles."""
        roles = []
        for rid in role_ids:
            role = Mock()
            role.id = rid
            roles.append(role)
        entity = Mock()
        entity.roles = roles
        return entity

    def test_no_roles_returns_base_only(self):
        type_entity = self._make_type_entity([])
        app_manager = Mock()

        result = RoleRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=app_manager,
            session=Mock(),
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert set(result) == {"user-1"}

    @patch("lys.apps.user_role.mixins.recipient_resolution.select")
    def test_roles_query_user_role_table(self, mock_select):
        type_entity = self._make_type_entity(["ADMIN_ROLE"])

        # Mock user_role entity
        user_role_entity = MagicMock()
        app_manager = Mock()
        app_manager.get_entity.return_value = user_role_entity

        # Mock select().where() chain
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        # Mock session.execute to return rows with user_ids
        session = Mock()
        session.execute.return_value = [("user-2",), ("user-3",)]

        result = RoleRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=app_manager,
            session=session,
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert set(result) == {"user-1", "user-2", "user-3"}
        app_manager.get_entity.assert_called_with("user_role", nullable=True)

    @patch("lys.apps.user_role.mixins.recipient_resolution.Base")
    def test_user_role_entity_and_table_not_found(self, mock_base):
        """When both entity and metadata table are missing, falls back to base."""
        type_entity = self._make_type_entity(["ADMIN_ROLE"])

        app_manager = Mock()
        app_manager.get_entity.return_value = None
        mock_base.metadata.tables.get.return_value = None

        result = RoleRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=app_manager,
            session=Mock(),
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        # Falls back to base resolution only
        assert set(result) == {"user-1"}

    @patch("lys.apps.user_role.mixins.recipient_resolution.select")
    def test_deduplication_with_roles(self, mock_select):
        type_entity = self._make_type_entity(["ADMIN_ROLE"])

        user_role_entity = MagicMock()
        app_manager = Mock()
        app_manager.get_entity.return_value = user_role_entity

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        # Role query returns user-1 again (same as triggered_by)
        session = Mock()
        session.execute.return_value = [("user-1",)]

        result = RoleRecipientResolutionMixin._resolve_recipients_sync(
            app_manager=app_manager,
            session=session,
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert result == ["user-1"]


class TestRoleRecipientResolutionMixinAsync:
    """Tests for async _resolve_recipients with role-based resolution."""

    def _make_type_entity(self, role_ids):
        roles = []
        for rid in role_ids:
            role = Mock()
            role.id = rid
            roles.append(role)
        entity = Mock()
        entity.roles = roles
        return entity

    @pytest.mark.asyncio
    async def test_no_roles_returns_base_only(self):
        type_entity = self._make_type_entity([])
        app_manager = Mock()

        result = await RoleRecipientResolutionMixin._resolve_recipients(
            app_manager=app_manager,
            session=AsyncMock(),
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert set(result) == {"user-1"}

    @pytest.mark.asyncio
    @patch("lys.apps.user_role.mixins.recipient_resolution.select")
    async def test_roles_query_user_role_table(self, mock_select):
        type_entity = self._make_type_entity(["ADMIN_ROLE"])

        user_role_entity = MagicMock()
        app_manager = Mock()
        app_manager.get_entity.return_value = user_role_entity

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        session = AsyncMock()
        session.execute.return_value = [("user-2",), ("user-3",)]

        result = await RoleRecipientResolutionMixin._resolve_recipients(
            app_manager=app_manager,
            session=session,
            type_entity=type_entity,
            triggered_by_user_id="user-1",
            additional_user_ids=None,
        )
        assert set(result) == {"user-1", "user-2", "user-3"}
