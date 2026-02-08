"""
Integration tests for user_role RoleService.

Tests cover:
- Role CRUD operations (ParametricEntity)
- Role-webservice relationships
"""

import pytest
from sqlalchemy import select


class TestRoleServiceCRUD:
    """Test RoleService CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_role_by_id(self, user_role_app_manager):
        """Test retrieving a role by its ID."""
        role_service = user_role_app_manager.get_service("role")

        async with user_role_app_manager.database.get_session() as session:
            role = await role_service.get_by_id("ROLE_A", session)
            assert role is not None
            assert role.id == "ROLE_A"
            assert role.enabled is True
            assert role.supervisor_only is False

    @pytest.mark.asyncio
    async def test_get_supervisor_only_role(self, user_role_app_manager):
        """Test retrieving a supervisor-only role."""
        role_service = user_role_app_manager.get_service("role")

        async with user_role_app_manager.database.get_session() as session:
            role = await role_service.get_by_id("SUPERVISOR_ONLY_ROLE", session)
            assert role is not None
            assert role.supervisor_only is True

    @pytest.mark.asyncio
    async def test_create_role(self, user_role_app_manager):
        """Test creating a new role."""
        role_service = user_role_app_manager.get_service("role")

        async with user_role_app_manager.database.get_session() as session:
            role = await role_service.create(
                session=session,
                id="NEW_TEST_ROLE",
                enabled=True,
                supervisor_only=False
            )
            assert role.id == "NEW_TEST_ROLE"
            assert role.enabled is True

    @pytest.mark.asyncio
    async def test_role_webservices_relationship(self, user_role_app_manager):
        """Test that role_webservices relationship is loaded correctly."""
        role_service = user_role_app_manager.get_service("role")

        async with user_role_app_manager.database.get_session() as session:
            role = await role_service.get_by_id("ROLE_A", session)
            assert len(role.role_webservices) == 1
            assert role.role_webservices[0].webservice_id == "ws_a"

    @pytest.mark.asyncio
    async def test_get_webservice_ids(self, user_role_app_manager):
        """Test the get_webservice_ids helper method."""
        role_service = user_role_app_manager.get_service("role")

        async with user_role_app_manager.database.get_session() as session:
            role = await role_service.get_by_id("ROLE_A", session)
            ws_ids = role.get_webservice_ids()
            assert ws_ids == ["ws_a"]
