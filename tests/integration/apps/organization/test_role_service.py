"""
Integration tests for organization OrganizationRoleService.

Tests cover:
- Supervisor-only roles hidden from client users and client owners
- Full list kept for supervisors and super users
- Caller filters combined with, never replaced by, the organization filter
"""

from uuid import uuid4

import pytest


async def _visible_role_ids(app_manager, connected_user, **filters) -> set[str]:
    role_service = app_manager.get_service("role")
    async with app_manager.database.get_session() as session:
        stmt = await role_service.visible_roles_statement(session, connected_user, **filters)
        return {role.id for role in (await session.execute(stmt)).scalars().all()}


async def _create_client(app_manager):
    client_service = app_manager.get_service("client")
    async with app_manager.database.get_session() as session:
        return await client_service.create_client_with_owner(
            session=session,
            client_name=f"Corp-{uuid4().hex[:8]}",
            email=f"owner-role-{uuid4().hex[:8]}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False
        )


async def _create_user(app_manager, client_id: str | None = None) -> str:
    user_service = app_manager.get_service("user")
    async with app_manager.database.get_session() as session:
        user = await user_service.create_user(
            session=session,
            email=f"user-role-{uuid4().hex[:8]}@example.com",
            password="Password123!",
            language_id="en",
            send_verification_email=False,
        )
        user.client_id = client_id
        await session.commit()
        return user.id


class TestOrganizationRoleServiceVisibleRoles:
    """Test OrganizationRoleService.visible_roles_statement."""

    @pytest.mark.asyncio
    async def test_service_is_overridden(self, organization_app_manager):
        """The organization app registers its own role service."""
        from lys.apps.organization.modules.role.services import OrganizationRoleService
        assert organization_app_manager.get_service("role") is OrganizationRoleService

    @pytest.mark.asyncio
    async def test_client_user_does_not_see_supervisor_only_roles(self, organization_app_manager):
        """A client user only sees roles assignable to client users."""
        client = await _create_client(organization_app_manager)
        user_id = await _create_user(organization_app_manager, client_id=client.id)

        role_ids = await _visible_role_ids(organization_app_manager, {"sub": user_id, "is_super_user": False})

        assert "NORMAL_ROLE" in role_ids
        assert "SUPERVISOR_ROLE" not in role_ids

    @pytest.mark.asyncio
    async def test_client_owner_does_not_see_supervisor_only_roles(self, organization_app_manager):
        """A client owner (client_id is None) is still an organization member."""
        client = await _create_client(organization_app_manager)

        role_ids = await _visible_role_ids(organization_app_manager, {"sub": client.owner_id, "is_super_user": False})

        assert "NORMAL_ROLE" in role_ids
        assert "SUPERVISOR_ROLE" not in role_ids

    @pytest.mark.asyncio
    async def test_supervisor_sees_supervisor_only_roles(self, organization_app_manager):
        """A supervisor (no client, not an owner, not a super user) keeps the full list."""
        user_id = await _create_user(organization_app_manager)

        role_ids = await _visible_role_ids(organization_app_manager, {"sub": user_id, "is_super_user": False})

        assert {"NORMAL_ROLE", "SUPERVISOR_ROLE"} <= role_ids

    @pytest.mark.asyncio
    async def test_super_user_sees_supervisor_only_roles(self, organization_app_manager):
        """A super user keeps the full list."""
        role_ids = await _visible_role_ids(organization_app_manager, {"sub": str(uuid4()), "is_super_user": True})

        assert {"NORMAL_ROLE", "SUPERVISOR_ROLE"} <= role_ids

    @pytest.mark.asyncio
    async def test_client_user_asking_for_supervisor_only_roles_gets_none(self, organization_app_manager):
        """The caller's filter is combined with the organization filter, not replaced by it."""
        client = await _create_client(organization_app_manager)
        user_id = await _create_user(organization_app_manager, client_id=client.id)

        role_ids = await _visible_role_ids(
            organization_app_manager, {"sub": user_id, "is_super_user": False}, supervisor_only=True
        )

        assert role_ids == set()
