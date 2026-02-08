"""
Integration tests for organization UserService.

Tests cover:
- Client user creation
- Client user role assignment
- Role updates (add, remove, sync, supervisor_only guard)
- Organization role queries
- User properties (is_supervisor, is_client_user, accessing_organizations)
"""

import pytest
from uuid import uuid4

from lys.core.errors import LysError


class TestUserServiceCreateClientUser:
    """Test UserService.create_client_user operations."""

    @pytest.mark.asyncio
    async def test_create_client_user_without_roles(self, organization_app_manager):
        """Test creating a client user without any roles."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-cu-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-cu-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en"
            )

            assert user.id is not None
            assert user.client_id == client.id
            assert user.is_client_user is True
            assert user.is_supervisor is False

    @pytest.mark.asyncio
    async def test_create_client_user_with_roles(self, organization_app_manager):
        """Test creating a client user with normal roles."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-cr-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-cr-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                role_codes=["NORMAL_ROLE"]
            )

        # Re-fetch user to get updated client_user_roles via selectin
        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            assert len(user.client_user_roles) == 1
            assert user.client_user_roles[0].role_id == "NORMAL_ROLE"

    @pytest.mark.asyncio
    async def test_create_client_user_with_supervisor_role_fails(self, organization_app_manager):
        """Test that assigning a supervisor_only role to client user raises error."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-sf-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.create_client_user(
                    session=session,
                    client_id=client.id,
                    email=f"user-sf-{uuid4().hex[:8]}@example.com",
                    password="Password123!",
                    language_id="en",
                    role_codes=["SUPERVISOR_ROLE"]
                )

            assert "SUPERVISOR_ONLY_ROLE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_client_user_with_private_data(self, organization_app_manager):
        """Test creating a client user with name and gender."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-pd-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-pd-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="fr",
                first_name="Alice",
                last_name="Martin",
                gender_id="F"
            )

            assert user.private_data.first_name == "Alice"
            assert user.private_data.last_name == "Martin"
            assert user.private_data.gender_id == "F"
            assert user.language_id == "fr"


class TestUserServiceUpdateClientUserRoles:
    """Test UserService.update_client_user_roles operations."""

    @pytest.mark.asyncio
    async def test_update_client_user_roles_add_role(self, organization_app_manager):
        """Test adding a role to a client user."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-ar-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-ar-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en"
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            assert len(user.client_user_roles) == 0
            await user_service.update_client_user_roles(user, ["NORMAL_ROLE"], session)
            await session.flush()

        # Re-fetch to see updated roles
        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            assert len(user.client_user_roles) == 1
            assert user.client_user_roles[0].role_id == "NORMAL_ROLE"

    @pytest.mark.asyncio
    async def test_update_client_user_roles_remove_role(self, organization_app_manager):
        """Test removing a role from a client user."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-rr-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-rr-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                role_codes=["NORMAL_ROLE"]
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            assert len(user.client_user_roles) == 1
            await user_service.update_client_user_roles(user, [], session)
            await session.flush()

        # Re-fetch to see updated roles
        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            assert len(user.client_user_roles) == 0

    @pytest.mark.asyncio
    async def test_update_client_user_roles_sync(self, organization_app_manager):
        """Test syncing roles (add + remove) for a client user."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-sync-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-sync-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                role_codes=["NORMAL_ROLE"]
            )

        # Replace NORMAL_ROLE with EXTRA_ROLE
        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            await user_service.update_client_user_roles(user, ["EXTRA_ROLE"], session)
            await session.flush()

        # Re-fetch to see updated roles
        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            role_ids = {cur.role_id for cur in user.client_user_roles}
            assert role_ids == {"EXTRA_ROLE"}

    @pytest.mark.asyncio
    async def test_update_client_user_roles_supervisor_only_fails(self, organization_app_manager):
        """Test that adding a supervisor_only role via update raises error."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-sup-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-sup-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en"
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            with pytest.raises(LysError) as exc_info:
                await user_service.update_client_user_roles(user, ["SUPERVISOR_ROLE"], session)

            assert "SUPERVISOR_ONLY_ROLE" in str(exc_info.value)


class TestUserServiceOrganizationRoles:
    """Test UserService.get_user_organization_roles."""

    @pytest.mark.asyncio
    async def test_get_user_organization_roles(self, organization_app_manager):
        """Test retrieving user organization roles."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-gor-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-gor-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                role_codes=["NORMAL_ROLE"]
            )

        async with organization_app_manager.database.get_session() as session:
            roles = await user_service.get_user_organization_roles(user.id, session)
            assert len(roles) == 1
            assert roles[0].role_id == "NORMAL_ROLE"

    @pytest.mark.asyncio
    async def test_get_user_organization_roles_with_webservice_filter(self, organization_app_manager):
        """Test retrieving user organization roles filtered by webservice."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-wsf-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-wsf-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                role_codes=["NORMAL_ROLE"]
            )

        async with organization_app_manager.database.get_session() as session:
            # Filter by existing webservice
            roles = await user_service.get_user_organization_roles(
                user.id, session, webservice_id="some_webservice"
            )
            assert len(roles) == 1

            # Filter by non-existing webservice
            roles = await user_service.get_user_organization_roles(
                user.id, session, webservice_id="nonexistent_webservice"
            )
            assert len(roles) == 0


class TestUserServiceProperties:
    """Test User entity properties."""

    @pytest.mark.asyncio
    async def test_supervisor_user_properties(self, organization_app_manager):
        """Test that a user without client_id is a supervisor."""
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=f"supervisor-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

            assert user.is_supervisor is True
            assert user.is_client_user is False
            assert user.accessing_organizations() == {}

    @pytest.mark.asyncio
    async def test_client_user_properties(self, organization_app_manager):
        """Test that a user with client_id is a client user."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"Corp-{uuid4().hex[:8]}",
                email=f"owner-prop-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_client_user(
                session=session,
                client_id=client.id,
                email=f"user-prop-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en"
            )

            assert user.is_supervisor is False
            assert user.is_client_user is True
            assert user.accessing_organizations() == {"client": [client.id]}
