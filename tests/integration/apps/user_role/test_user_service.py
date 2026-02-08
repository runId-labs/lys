"""
Integration tests for user_role UserService.

Tests cover:
- User creation with roles
- Role update operations (add, remove, sync)
- Super user role update guard
"""

import pytest
from uuid import uuid4

from lys.core.errors import LysError


class TestUserServiceCreateWithRoles:
    """Test UserService.create_user with role assignment."""

    @pytest.mark.asyncio
    async def test_create_user_without_roles(self, user_role_app_manager):
        """Test creating a user without any roles."""
        user_service = user_role_app_manager.get_service("user")

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"noroles-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

            assert user.id is not None
            assert len(user.roles) == 0

    @pytest.mark.asyncio
    async def test_create_user_with_roles(self, user_role_app_manager):
        """Test creating a user with roles assigned."""
        user_service = user_role_app_manager.get_service("user")

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"withroles-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False,
                roles=["ROLE_A", "ROLE_B"]
            )

            role_ids = {r.id for r in user.roles}
            assert role_ids == {"ROLE_A", "ROLE_B"}


class TestUserServiceUpdateRoles:
    """Test UserService.update_user_roles operations."""

    @pytest.mark.asyncio
    async def test_update_user_roles_add(self, user_role_app_manager):
        """Test adding roles to a user."""
        user_service = user_role_app_manager.get_service("user")

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"addrole-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            assert len(user.roles) == 0

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            await user_service.update_user_roles(user, ["ROLE_A"], session)
            await session.flush()

            role_ids = {r.id for r in user.roles}
            assert role_ids == {"ROLE_A"}

    @pytest.mark.asyncio
    async def test_update_user_roles_remove(self, user_role_app_manager):
        """Test removing all roles from a user."""
        user_service = user_role_app_manager.get_service("user")

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"removerole-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False,
                roles=["ROLE_A"]
            )
            assert len(user.roles) == 1

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            await user_service.update_user_roles(user, [], session)
            await session.flush()

            assert len(user.roles) == 0

    @pytest.mark.asyncio
    async def test_update_user_roles_sync(self, user_role_app_manager):
        """Test syncing roles (add + remove simultaneously)."""
        user_service = user_role_app_manager.get_service("user")

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"syncrole-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False,
                roles=["ROLE_A"]
            )

        # Replace ROLE_A with ROLE_B
        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            await user_service.update_user_roles(user, ["ROLE_B"], session)
            await session.flush()

            role_ids = {r.id for r in user.roles}
            assert role_ids == {"ROLE_B"}

    @pytest.mark.asyncio
    async def test_update_super_user_roles_fails(self, user_role_app_manager):
        """Test that updating roles for a super user raises error."""
        user_service = user_role_app_manager.get_service("user")

        async with user_role_app_manager.database.get_session() as session:
            super_user = await user_service.create_super_user(
                session=session,
                email=f"super-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(super_user.id, session)
            with pytest.raises(LysError) as exc_info:
                await user_service.update_user_roles(user, ["ROLE_A"], session)

            assert "CANNOT_UPDATE_SUPER_USER_ROLES" in str(exc_info.value)
