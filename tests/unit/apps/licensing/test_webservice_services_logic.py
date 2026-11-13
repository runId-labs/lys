"""
Unit tests for LicensingWebserviceService logic.

On a licensed webservice, the OWNER access level requires a license.
SQL conditions (_owner_access_condition, _user_is_licensed_condition) are tested at integration level.

Isolation: inline imports + patch.object. No global state modified.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")


class TestCanAccessAsOwner:
    """LicensingWebserviceService._can_access_as_owner()."""

    @pytest.mark.asyncio
    async def test_non_licensed_webservice_is_open_without_any_query(self):
        from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService

        with patch.object(LicensingWebserviceService, "user_is_licensed", new_callable=AsyncMock) as licensed:
            allowed = await LicensingWebserviceService._can_access_as_owner(
                SimpleNamespace(is_licenced=False), {"sub": "user-1"}, AsyncMock()
            )

        assert allowed is True
        licensed.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("has_license", [True, False])
    async def test_licensed_webservice_follows_the_user_license(self, has_license):
        from lys.apps.licensing.modules.webservice.services import LicensingWebserviceService

        with patch.object(
            LicensingWebserviceService, "user_is_licensed", new_callable=AsyncMock, return_value=has_license
        ):
            allowed = await LicensingWebserviceService._can_access_as_owner(
                SimpleNamespace(is_licenced=True), {"sub": "user-1"}, AsyncMock()
            )

        assert allowed is has_license
