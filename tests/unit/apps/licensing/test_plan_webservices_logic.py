"""
Unit tests for licensing plan webservices logic.

Tests LicensePlanQuery.all_active_license_plans() resolver logic directly.
The resolver builds SQLAlchemy queries, so we patch select() and test
the branching logic (owner, member, no client).
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


def _get_resolver():
    """Get the raw resolver function from the query.

    lys_connection wraps the original function in an inner_resolver closure.
    The original resolver is stored in the closure as 'resolver' freevar.
    """
    from lys.apps.licensing.modules.plan.webservices import LicensePlanQuery
    wrapped = LicensePlanQuery.__dict__["all_active_license_plans"]
    idx = wrapped.__code__.co_freevars.index("resolver")
    return wrapped.__closure__[idx].cell_contents


class TestAllActiveLicensePlans:
    """Tests for LicensePlanQuery.all_active_license_plans() logic."""

    def _setup_info(self, user_id="user-123"):
        mock_info = MagicMock()
        mock_info.context.connected_user = {"sub": user_id}
        mock_info.context.session = AsyncMock()

        mock_plan_entity = MagicMock()
        mock_client_entity = MagicMock()
        mock_user_entity = MagicMock()

        def get_entity(name):
            return {
                "license_plan": mock_plan_entity,
                "client": mock_client_entity,
                "user": mock_user_entity,
            }[name]

        mock_info.context.app_manager.get_entity.side_effect = get_entity

        return mock_info, mock_plan_entity, mock_client_entity, mock_user_entity

    @patch("lys.apps.licensing.modules.plan.webservices.select")
    @patch("lys.apps.licensing.modules.plan.webservices.or_")
    def test_user_without_client_gets_global_plans_only(self, mock_or, mock_select):
        resolver = _get_resolver()
        mock_info, mock_plan_entity, _, _ = self._setup_info()

        # Both queries return None (user is not owner nor member)
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None

        mock_info.context.session.execute = AsyncMock(
            side_effect=[mock_result1, mock_result2]
        )

        # Make select().where().order_by() chain work
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(resolver(None, info=mock_info))
        finally:
            loop.close()

        # Two session.execute calls: check owner, check member
        assert mock_info.context.session.execute.call_count == 2
        # or_ should NOT be called (no client → global plans only)
        mock_or.assert_not_called()
        assert result is not None

    @patch("lys.apps.licensing.modules.plan.webservices.select")
    @patch("lys.apps.licensing.modules.plan.webservices.or_")
    def test_user_as_owner_gets_global_and_custom_plans(self, mock_or, mock_select):
        resolver = _get_resolver()
        mock_info, _, _, _ = self._setup_info()

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = "client-uuid"

        mock_info.context.session.execute = AsyncMock(return_value=mock_result1)

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(resolver(None, info=mock_info))
        finally:
            loop.close()

        # Only one execute call (found owner immediately)
        assert mock_info.context.session.execute.call_count == 1
        # or_ should be called (has client → global + custom)
        mock_or.assert_called_once()
        assert result is not None

    @patch("lys.apps.licensing.modules.plan.webservices.select")
    @patch("lys.apps.licensing.modules.plan.webservices.or_")
    def test_user_as_member_gets_global_and_custom_plans(self, mock_or, mock_select):
        resolver = _get_resolver()
        mock_info, _, _, _ = self._setup_info()

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None

        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = "client-uuid"

        mock_info.context.session.execute = AsyncMock(
            side_effect=[mock_result1, mock_result2]
        )

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(resolver(None, info=mock_info))
        finally:
            loop.close()

        # Two execute calls: owner check failed, member check succeeded
        assert mock_info.context.session.execute.call_count == 2
        # or_ should be called (has client → global + custom)
        mock_or.assert_called_once()
        assert result is not None

    @patch("lys.apps.licensing.modules.plan.webservices.select")
    def test_entities_resolved_via_app_manager(self, mock_select):
        resolver = _get_resolver()
        mock_info, _, _, _ = self._setup_info()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_info.context.session.execute = AsyncMock(return_value=mock_result)

        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(resolver(None, info=mock_info))
        finally:
            loop.close()

        calls = [c.args[0] for c in mock_info.context.app_manager.get_entity.call_args_list]
        assert "license_plan" in calls
        assert "client" in calls
        assert "user" in calls
