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


async def _visible_roles(role_service, session, connected_user, **filters) -> list:
    stmt = await role_service.visible_roles_statement(session, connected_user, **filters)
    return list((await session.execute(stmt)).scalars().all())


class TestRoleServiceVisibleRoles:
    """Test RoleService.visible_roles_statement without the organization app."""

    @pytest.mark.asyncio
    async def test_regular_user_sees_supervisor_only_roles(self, user_role_app_manager):
        """A user who is not a super user still sees supervisor-only roles (internal team)."""
        role_service = user_role_app_manager.get_service("role")
        connected_user = {"sub": "any-user", "is_super_user": False}

        async with user_role_app_manager.database.get_session() as session:
            roles = await _visible_roles(role_service, session, connected_user)
            role_ids = [role.id for role in roles]

        assert {"ROLE_A", "ROLE_B", "SUPERVISOR_ONLY_ROLE"} <= set(role_ids)
        assert role_ids == sorted(role_ids)

    @pytest.mark.asyncio
    async def test_supervisor_only_filter(self, user_role_app_manager):
        """The supervisor_only filter is applied as given."""
        role_service = user_role_app_manager.get_service("role")
        connected_user = {"sub": "any-user", "is_super_user": False}

        async with user_role_app_manager.database.get_session() as session:
            supervisor_roles = await _visible_roles(role_service, session, connected_user, supervisor_only=True)
            client_roles = await _visible_roles(role_service, session, connected_user, supervisor_only=False)

        assert all(role.supervisor_only for role in supervisor_roles)
        assert "SUPERVISOR_ONLY_ROLE" in {role.id for role in supervisor_roles}
        assert not any(role.supervisor_only for role in client_roles)

    @pytest.mark.asyncio
    async def test_enabled_filter(self, user_role_app_manager):
        """The enabled filter is applied as given."""
        role_service = user_role_app_manager.get_service("role")
        connected_user = {"sub": "any-user", "is_super_user": False}

        async with user_role_app_manager.database.get_session() as session:
            await role_service.create(session=session, id="DISABLED_VISIBLE_ROLE", enabled=False)
            await session.commit()

        async with user_role_app_manager.database.get_session() as session:
            enabled_ids = {r.id for r in await _visible_roles(role_service, session, connected_user, enabled=True)}
            disabled_ids = {r.id for r in await _visible_roles(role_service, session, connected_user, enabled=False)}

        assert "DISABLED_VISIBLE_ROLE" not in enabled_ids
        assert "DISABLED_VISIBLE_ROLE" in disabled_ids
