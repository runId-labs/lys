"""
Unit tests for core utils database module.

Tests check_is_needing_session and get_select_total_count.
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.core.utils.database import check_is_needing_session, get_select_total_count


class TestCheckIsNeedingSession:
    """Tests for check_is_needing_session function."""

    def test_returns_true_for_async_session_annotation(self):
        """Test returns True when method has session: AsyncSession."""
        async def method(session: AsyncSession):
            pass

        assert check_is_needing_session(method) is True

    def test_returns_true_for_sync_session_annotation(self):
        """Test returns True when method has session: Session."""
        def method(session: Session):
            pass

        assert check_is_needing_session(method) is True

    def test_returns_false_when_no_session_param(self):
        """Test returns False when method has no session parameter."""
        def method(value: str):
            pass

        assert check_is_needing_session(method) is False

    def test_returns_false_when_session_has_wrong_type(self):
        """Test returns False when session param has non-session type."""
        def method(session: str):
            pass

        assert check_is_needing_session(method) is False


class TestGetSelectTotalCount:
    """Tests for get_select_total_count function."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_returns_count_with_where_clause(self):
        """Test get_select_total_count returns scalar count when stmt has whereclause."""
        from sqlalchemy import table, column

        mock_table = table("my_table", column("id"))

        mock_entity = MagicMock()
        mock_entity.id = MagicMock()
        mock_entity.id.distinct.return_value = column("id")

        mock_stmt = MagicMock()
        mock_stmt.get_final_froms.return_value = [mock_table]
        mock_where = column("id") == 1
        mock_stmt.whereclause = mock_where

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = self._run(get_select_total_count(mock_stmt, mock_entity, mock_session))
        assert result == 42
        mock_session.execute.assert_awaited_once()

    def test_returns_count_without_where_clause(self):
        """Test get_select_total_count returns count when stmt has no whereclause."""
        from sqlalchemy import table, column

        mock_table = table("my_table", column("id"))

        mock_entity = MagicMock()
        mock_entity.id = MagicMock()
        mock_entity.id.distinct.return_value = column("id")

        mock_stmt = MagicMock()
        mock_stmt.get_final_froms.return_value = [mock_table]
        mock_stmt.whereclause = None

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        result = self._run(get_select_total_count(mock_stmt, mock_entity, mock_session))
        assert result == 10
