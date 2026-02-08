"""
Integration tests for organization ClientService.

Tests cover:
- Client creation with owner
- Duplicate email detection
- Owner checking
- Organization properties
"""

import pytest
from uuid import uuid4

from lys.core.errors import LysError


class TestClientServiceCreateClientWithOwner:
    """Test ClientService.create_client_with_owner operations."""

    @pytest.mark.asyncio
    async def test_create_client_with_owner(self, organization_app_manager):
        """Test creating a client with an owner user."""
        client_service = organization_app_manager.get_service("client")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name="Test Corp",
                email=f"owner-{uuid4().hex[:8]}@example.com",
                password="SecurePassword123!",
                language_id="en",
                send_verification_email=False,
                first_name="John",
                last_name="Doe"
            )

            assert client.id is not None
            assert client.name == "Test Corp"
            assert client.owner_id is not None
            assert client.owner is not None
            assert client.owner.client_id == client.id
            assert client.owner.password.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_create_client_with_owner_duplicate_email(self, organization_app_manager):
        """Test that creating a client with duplicate owner email raises error."""
        client_service = organization_app_manager.get_service("client")
        email = f"dup-{uuid4().hex[:8]}@example.com"

        async with organization_app_manager.database.get_session() as session:
            await client_service.create_client_with_owner(
                session=session,
                client_name="First Corp",
                email=email,
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await client_service.create_client_with_owner(
                    session=session,
                    client_name="Second Corp",
                    email=email,
                    password="Password456!",
                    language_id="en",
                    send_verification_email=False
                )

            assert "USER_ALREADY_EXISTS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_client_with_owner_sets_private_data(self, organization_app_manager):
        """Test that owner private data is correctly set."""
        client_service = organization_app_manager.get_service("client")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name="Data Corp",
                email=f"data-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="fr",
                send_verification_email=False,
                first_name="Marie",
                last_name="Dupont",
                gender_id="F"
            )

            assert client.owner.private_data.first_name == "Marie"
            assert client.owner.private_data.last_name == "Dupont"
            assert client.owner.private_data.gender_id == "F"
            assert client.owner.language_id == "fr"


class TestClientServiceOwnerChecks:
    """Test ClientService ownership checks."""

    @pytest.mark.asyncio
    async def test_user_is_client_owner_true(self, organization_app_manager):
        """Test that user_is_client_owner returns True for an owner."""
        client_service = organization_app_manager.get_service("client")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name="Owner Corp",
                email=f"owner-check-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        async with organization_app_manager.database.get_session() as session:
            is_owner = await client_service.user_is_client_owner(client.owner_id, session)
            assert is_owner is True

    @pytest.mark.asyncio
    async def test_user_is_client_owner_false(self, organization_app_manager):
        """Test that user_is_client_owner returns False for a non-owner."""
        client_service = organization_app_manager.get_service("client")
        fake_user_id = str(uuid4())

        async with organization_app_manager.database.get_session() as session:
            is_owner = await client_service.user_is_client_owner(fake_user_id, session)
            assert is_owner is False


class TestClientServiceOrganizationProperties:
    """Test Client organization properties."""

    @pytest.mark.asyncio
    async def test_parent_organization_returns_none(self, organization_app_manager):
        """Test that Client.parent_organization returns None (top-level)."""
        client_service = organization_app_manager.get_service("client")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name="Top Level Corp",
                email=f"parent-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

            assert client.parent_organization is None

    @pytest.mark.asyncio
    async def test_organization_accessing_filters(self, organization_app_manager):
        """Test that organization_accessing_filters applies correct filters."""
        client_entity = organization_app_manager.get_entity("client")
        from sqlalchemy import select

        stmt = select(client_entity)
        org_ids = {"client": ["test-client-id-1", "test-client-id-2"]}

        filtered_stmt, conditions = client_entity.organization_accessing_filters(stmt, org_ids)
        assert len(conditions) == 1
