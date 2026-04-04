"""
Integration tests for AuthWebserviceService.accessible_webservices.

Tests that disabled webservices are excluded from query results.
"""

import pytest

from lys.core.models.webservices import WebserviceFixturesModel


class TestAccessibleWebservicesFilterDisabled:
    """Test that accessible_webservices excludes disabled webservices."""

    @pytest.mark.asyncio
    async def test_disabled_webservices_excluded_for_super_user(self, user_auth_app_manager):
        """Disabled webservices should not appear even for super users."""
        webservice_service = user_auth_app_manager.get_service("webservice")

        # Create access levels needed by webservices
        access_level_service = user_auth_app_manager.get_service("access_level")
        async with user_auth_app_manager.database.get_session() as session:
            await access_level_service.create(session=session, id="CONNECTED", enabled=True)
            await session.commit()

        ws_configs = [
            WebserviceFixturesModel(
                id="ws_enabled",
                attributes=WebserviceFixturesModel.AttributesModel(
                    public_type="query",
                    is_licenced=False,
                    enabled=True,
                    access_levels=["CONNECTED"],
                    operation_type="query",
                    ai_tool=None
                )
            ),
            WebserviceFixturesModel(
                id="ws_disabled",
                attributes=WebserviceFixturesModel.AttributesModel(
                    public_type="query",
                    is_licenced=False,
                    enabled=False,
                    access_levels=["CONNECTED"],
                    operation_type="query",
                    ai_tool=None
                )
            ),
        ]

        async with user_auth_app_manager.database.get_session() as session:
            await webservice_service.register_webservices(ws_configs, "test_app", session)
            await session.commit()

        # Super user should see enabled but not disabled
        super_user = {"sub": "admin-1", "is_super_user": True}
        stmt = await webservice_service.accessible_webservices(user=super_user)

        async with user_auth_app_manager.database.get_session() as session:
            result = await session.execute(stmt)
            webservices = result.scalars().all()

        ws_ids = [ws.id for ws in webservices]
        assert "ws_enabled" in ws_ids
        assert "ws_disabled" not in ws_ids

    @pytest.mark.asyncio
    async def test_disabled_webservices_excluded_for_anonymous(self, user_auth_app_manager):
        """Disabled webservices should not appear for anonymous users."""
        webservice_service = user_auth_app_manager.get_service("webservice")

        stmt = await webservice_service.accessible_webservices(user=None)

        async with user_auth_app_manager.database.get_session() as session:
            result = await session.execute(stmt)
            webservices = result.scalars().all()

        ws_ids = [ws.id for ws in webservices]
        assert "ws_disabled" not in ws_ids

    @pytest.mark.asyncio
    async def test_disabled_webservices_excluded_for_regular_user(self, user_auth_app_manager):
        """Disabled webservices should not appear for regular users."""
        webservice_service = user_auth_app_manager.get_service("webservice")

        regular_user = {"sub": "user-123", "is_super_user": False}
        stmt = await webservice_service.accessible_webservices(user=regular_user)

        async with user_auth_app_manager.database.get_session() as session:
            result = await session.execute(stmt)
            webservices = result.scalars().all()

        ws_ids = [ws.id for ws in webservices]
        assert "ws_disabled" not in ws_ids