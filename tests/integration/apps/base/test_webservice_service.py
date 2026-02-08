"""
Integration tests for base WebserviceService.

Tests cover:
- register_webservices (new, update, count)
"""

import pytest

from lys.core.models.webservices import WebserviceFixturesModel


class TestWebserviceServiceRegister:
    """Test WebserviceService.register_webservices."""

    @pytest.mark.asyncio
    async def test_register_new_webservices(self, user_auth_app_manager):
        """Test registering new webservices."""
        webservice_service = user_auth_app_manager.get_service("webservice")

        # Create access levels needed by webservices
        access_level_service = user_auth_app_manager.get_service("access_level")
        async with user_auth_app_manager.database.get_session() as session:
            await access_level_service.create(session=session, id="CONNECTED", enabled=True)
            await session.commit()

        ws_configs = [
            WebserviceFixturesModel(
                id="test_ws_1",
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
                id="test_ws_2",
                attributes=WebserviceFixturesModel.AttributesModel(
                    public_type="mutation",
                    is_licenced=True,
                    enabled=True,
                    access_levels=["CONNECTED"],
                    operation_type="mutation",
                    ai_tool=None
                )
            )
        ]

        async with user_auth_app_manager.database.get_session() as session:
            count = await webservice_service.register_webservices(
                ws_configs, "test_app", session
            )
            await session.commit()

        assert count == 2

        # Verify webservices were created
        async with user_auth_app_manager.database.get_session() as session:
            ws1 = await webservice_service.get_by_id("test_ws_1", session)
            assert ws1 is not None
            assert ws1.app_name == "test_app"
            assert ws1.is_licenced is False
            assert ws1.operation_type == "query"

    @pytest.mark.asyncio
    async def test_register_existing_webservices_updates(self, user_auth_app_manager):
        """Test that re-registering updates existing webservices."""
        webservice_service = user_auth_app_manager.get_service("webservice")

        ws_configs = [
            WebserviceFixturesModel(
                id="test_ws_1",
                attributes=WebserviceFixturesModel.AttributesModel(
                    public_type="query",
                    is_licenced=True,  # Changed from False
                    enabled=True,
                    access_levels=["CONNECTED"],
                    operation_type="query",
                    ai_tool={"name": "test_tool"}  # Added
                )
            )
        ]

        async with user_auth_app_manager.database.get_session() as session:
            count = await webservice_service.register_webservices(
                ws_configs, "updated_app", session
            )
            await session.commit()

        assert count == 1

        async with user_auth_app_manager.database.get_session() as session:
            ws = await webservice_service.get_by_id("test_ws_1", session)
            assert ws.is_licenced is True
            assert ws.app_name == "updated_app"
            assert ws.ai_tool == {"name": "test_tool"}

    @pytest.mark.asyncio
    async def test_register_webservices_returns_count(self, user_auth_app_manager):
        """Test that register_webservices returns correct count."""
        webservice_service = user_auth_app_manager.get_service("webservice")

        ws_configs = [
            WebserviceFixturesModel(
                id=f"count_ws_{i}",
                attributes=WebserviceFixturesModel.AttributesModel(
                    public_type="query",
                    is_licenced=False,
                    enabled=True,
                    access_levels=[],
                    operation_type="query",
                    ai_tool=None
                )
            )
            for i in range(3)
        ]

        async with user_auth_app_manager.database.get_session() as session:
            count = await webservice_service.register_webservices(
                ws_configs, "count_app", session
            )

        assert count == 3
