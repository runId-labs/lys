"""
Unit tests for core utils access module.

Tests cover check_access_to_object for entities attached to an AsyncSession
(permission check delegated to run_sync so lazy loads stay greenlet-safe) and
for detached entities (permission check called directly).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def build_context(user_id="user-1", access_type=None):
    """Build a minimal context exposing connected_user and access_type."""
    context = MagicMock()
    context.connected_user = {"sub": user_id} if user_id else None
    context.access_type = access_type if access_type is not None else True
    context.webservice_name = "test_webservice"
    return context


def build_session():
    """Build an AsyncSession stub whose run_sync executes the callback synchronously."""
    session = MagicMock()
    session.run_sync = AsyncMock(side_effect=lambda fn: fn(session))
    return session


class TestCheckAccessToObjectAttached:
    """Tests for entities still attached to a session."""

    @pytest.mark.asyncio
    async def test_permission_checked_through_run_sync(self):
        """Test the permission check is delegated to session.run_sync."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True
        session = build_session()

        with patch("lys.core.utils.access.async_object_session", return_value=session):
            result = await check_access_to_object(entity_obj, build_context())

        assert result is True
        session.run_sync.assert_awaited_once()
        entity_obj.check_permission.assert_called_once_with("user-1", True)

    @pytest.mark.asyncio
    async def test_permission_not_called_outside_run_sync(self):
        """Test check_permission only runs from the callback given to run_sync."""
        from lys.core.utils.access import check_access_to_object

        captured = {}

        async def capture(fn):
            # the callback has not been executed yet: check_permission must not have run
            captured["fn"] = fn
            assert not entity_obj.check_permission.called
            return fn(session)

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True
        session = MagicMock()
        session.run_sync = AsyncMock(side_effect=capture)

        with patch("lys.core.utils.access.async_object_session", return_value=session):
            await check_access_to_object(entity_obj, build_context())

        assert captured["fn"] is not None
        entity_obj.check_permission.assert_called_once_with("user-1", True)

    @pytest.mark.asyncio
    async def test_denied_permission_raises(self):
        """Test a False result from run_sync raises a permission error."""
        from lys.core.utils.access import check_access_to_object
        from lys.core.errors import LysError
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = False
        session = build_session()

        with patch("lys.core.utils.access.async_object_session", return_value=session):
            with pytest.raises(LysError) as exc_info:
                await check_access_to_object(entity_obj, build_context())

        assert exc_info.value.status_code == PERMISSION_DENIED_ERROR[0]


class TestCheckAccessToObjectDetached:
    """Tests for entities no longer attached to a session."""

    @pytest.mark.asyncio
    async def test_permission_checked_directly(self):
        """Test check_permission is called directly when no session is found."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True

        with patch("lys.core.utils.access.async_object_session", return_value=None):
            result = await check_access_to_object(entity_obj, build_context())

        assert result is True
        entity_obj.check_permission.assert_called_once_with("user-1", True)

    @pytest.mark.asyncio
    async def test_denied_permission_raises(self):
        """Test a False result without session raises a permission error."""
        from lys.core.utils.access import check_access_to_object
        from lys.core.errors import LysError
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = False

        with patch("lys.core.utils.access.async_object_session", return_value=None):
            with pytest.raises(LysError) as exc_info:
                await check_access_to_object(entity_obj, build_context())

        assert exc_info.value.status_code == PERMISSION_DENIED_ERROR[0]

    @pytest.mark.asyncio
    async def test_no_connected_user_passes_none(self):
        """Test a missing connected user results in a None user id."""
        from lys.core.utils.access import check_access_to_object

        entity_obj = MagicMock()
        entity_obj.check_permission.return_value = True

        with patch("lys.core.utils.access.async_object_session", return_value=None):
            await check_access_to_object(entity_obj, build_context(user_id=None))

        entity_obj.check_permission.assert_called_once_with(None, True)
