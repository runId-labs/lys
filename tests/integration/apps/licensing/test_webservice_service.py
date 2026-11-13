"""
Integration tests for LicensingWebserviceService: OWNER on a licensed webservice requires a license.

Covers the SQL side (_user_is_licensed_condition through user_is_licensed and
accessible_webservices) and its Python counterpart (get_user_access_levels).
"""
import pytest

from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
from tests.integration.apps.licensing.conftest import (
    LICENSED_PROFILES, create_license_profile_users, register_owner_webservices
)


class TestUserIsLicensed:
    """LicensingWebserviceService.user_is_licensed (SQL condition)."""

    @pytest.mark.asyncio
    async def test_license_by_profile(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)
        webservice_service = licensing_app_manager.get_service("webservice")

        async with licensing_app_manager.database.get_session() as session:
            for profile, expected in LICENSED_PROFILES.items():
                assert await webservice_service.user_is_licensed(users[profile], session) is expected, profile


class TestAccessibleWebservicesOwner:
    """accessible_webservices: the OWNER path to a licensed webservice needs a license."""

    @pytest.mark.asyncio
    async def test_owner_path_by_profile(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)
        licensed_ws, free_ws = await register_owner_webservices(licensing_app_manager)
        webservice_service = licensing_app_manager.get_service("webservice")

        for profile, has_license in LICENSED_PROFILES.items():
            stmt = await webservice_service.accessible_webservices(
                user={"sub": users[profile], "is_super_user": False}
            )
            async with licensing_app_manager.database.get_session() as session:
                ws_ids = {ws.id for ws in (await session.execute(stmt)).scalars().all()}

            assert free_ws in ws_ids, profile
            assert (licensed_ws in ws_ids) is has_license, profile


class TestGetUserAccessLevelsOwner:
    """get_user_access_levels: Python counterpart, must agree with the SQL side."""

    @pytest.mark.asyncio
    async def test_owner_level_by_profile(self, licensing_app_manager):
        users = await create_license_profile_users(licensing_app_manager)
        licensed_ws, free_ws = await register_owner_webservices(licensing_app_manager)
        webservice_service = licensing_app_manager.get_service("webservice")

        async with licensing_app_manager.database.get_session() as session:
            licensed = await webservice_service.get_by_id(licensed_ws, session)
            free = await webservice_service.get_by_id(free_ws, session)

            for profile, has_license in LICENSED_PROFILES.items():
                user = {"sub": users[profile], "is_super_user": False}
                licensed_levels = [al.id for al in await webservice_service.get_user_access_levels(
                    licensed, user, session
                )]
                free_levels = [al.id for al in await webservice_service.get_user_access_levels(
                    free, user, session
                )]

                assert OWNER_ACCESS_LEVEL in free_levels, profile
                assert (OWNER_ACCESS_LEVEL in licensed_levels) is has_license, profile
