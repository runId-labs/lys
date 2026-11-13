"""
Unit tests for user_auth webservice services logic.

Tests that AuthWebserviceService.accessible_webservices references
the enabled column for filtering disabled webservices, and that the OWNER
access level follows the _can_access_as_owner hook.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import inspect
import textwrap
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from lys.apps.user_auth.modules.webservice.services import AuthWebserviceService


class TestAccessibleWebservicesEnabledFilter:
    """Tests that accessible_webservices filters on the enabled column."""

    def test_accessible_webservices_references_enabled_filter(self):
        """Test that the source code of accessible_webservices filters on enabled."""
        source = inspect.getsource(AuthWebserviceService.accessible_webservices)
        assert "enabled" in source, "accessible_webservices must filter on the enabled column"

    def test_accessible_webservices_uses_is_true(self):
        """Test that the enabled filter uses .is_(True) for SQLAlchemy idiom."""
        source = inspect.getsource(AuthWebserviceService.accessible_webservices)
        assert ".is_(True)" in source, "enabled filter should use .is_(True) instead of == True"


class TestOwnerAccessHook:
    """AuthWebserviceService.get_user_access_levels() lists OWNER only when the hook allows it."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("owner_allowed", [True, False])
    async def test_owner_level_follows_the_hook(self, owner_allowed):
        from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL

        webservice = SimpleNamespace(
            id="all_things",
            access_levels=[
                SimpleNamespace(id=CONNECTED_ACCESS_LEVEL, enabled=True),
                SimpleNamespace(id=OWNER_ACCESS_LEVEL, enabled=True),
            ],
        )
        with (
            patch(
                "lys.apps.base.modules.webservice.services.WebserviceService.get_user_access_levels",
                new_callable=AsyncMock, return_value=[],
            ),
            patch.object(
                AuthWebserviceService, "_can_access_as_owner", new_callable=AsyncMock, return_value=owner_allowed
            ),
        ):
            levels = await AuthWebserviceService.get_user_access_levels(
                webservice, {"sub": "user-1", "is_super_user": False}, AsyncMock()
            )

        codes = [level.id for level in levels]
        assert CONNECTED_ACCESS_LEVEL in codes
        assert (OWNER_ACCESS_LEVEL in codes) is owner_allowed

    @pytest.mark.asyncio
    async def test_default_hook_opens_owner_to_every_connected_user(self):
        allowed = await AuthWebserviceService._can_access_as_owner(
            SimpleNamespace(is_licenced=True), {"sub": "user-1"}, AsyncMock()
        )
        assert allowed is True
