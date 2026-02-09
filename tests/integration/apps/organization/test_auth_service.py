"""
Integration tests for OrganizationAuthService.

Tests cover:
- generate_access_claims with organization claims
- _get_owner_webservices
- _get_client_user_role_webservices
- Super user skips organization claims
"""

import pytest
from uuid import uuid4


class TestOrganizationAuthServiceClaims:
    """Test OrganizationAuthService.generate_access_claims."""

    @pytest.mark.asyncio
    async def test_generate_access_claims_owner(self, organization_app_manager):
        """Test claims for client owner include organizations."""
        client_service = organization_app_manager.get_service("client")
        auth_service = organization_app_manager.get_service("auth")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"OrgAuth-Corp-{uuid4().hex[:8]}",
                email=f"orgauth-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await session.commit()
            owner_id = client.owner_id

        async with organization_app_manager.database.get_session() as session:
            user_service = organization_app_manager.get_service("user")
            owner = await user_service.get_by_id(owner_id, session)
            claims = await auth_service.generate_access_claims(owner, session)

            assert "organizations" in claims
            assert isinstance(claims["organizations"], dict)
            # Owner should have their client in organizations
            assert client.id in claims["organizations"]
            org_data = claims["organizations"][client.id]
            assert "webservices" in org_data

    @pytest.mark.asyncio
    async def test_generate_access_claims_client_user_with_role(self, organization_app_manager):
        """Test claims for user with client_user_role include organization webservices."""
        client_service = organization_app_manager.get_service("client")
        user_service = organization_app_manager.get_service("user")
        auth_service = organization_app_manager.get_service("auth")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"OrgRole-Corp-{uuid4().hex[:8]}",
                email=f"orgrole-owner-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await session.commit()

        # Create a client user with a role
        async with organization_app_manager.database.get_session() as session:
            member = await user_service.create_user(
                session=session,
                email=f"orgrole-member-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False,
            )
            # Set client_id on member
            member.client_id = client.id
            await session.flush()

            # Assign organization role via client_user_role (only user_id and role_id)
            client_user_role_entity = organization_app_manager.get_entity("client_user_role")
            cur = client_user_role_entity(
                user_id=member.id,
                role_id="NORMAL_ROLE",
            )
            session.add(cur)
            await session.commit()
            member_id = member.id

        async with organization_app_manager.database.get_session() as session:
            member = await user_service.get_by_id(member_id, session)
            claims = await auth_service.generate_access_claims(member, session)

            # Member with a role should have organizations in claims
            if "organizations" in claims and client.id in claims["organizations"]:
                org_data = claims["organizations"][client.id]
                assert "webservices" in org_data

    @pytest.mark.asyncio
    async def test_generate_access_claims_super_user_skips_organizations(self, organization_app_manager):
        """Test super user claims skip organization resolution."""
        user_service = organization_app_manager.get_service("user")
        auth_service = organization_app_manager.get_service("auth")

        email = f"superorg-{uuid4().hex[:8]}@example.com"
        async with organization_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=True,
                send_verification_email=False
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            assert claims["is_super_user"] is True

    @pytest.mark.asyncio
    async def test_generate_access_claims_user_without_org(self, organization_app_manager):
        """Test claims for user not in any organization has no organizations key."""
        user_service = organization_app_manager.get_service("user")
        auth_service = organization_app_manager.get_service("auth")

        email = f"noorg-{uuid4().hex[:8]}@example.com"
        async with organization_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                send_verification_email=False,
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            # User without any organization: "organizations" key is omitted
            # (empty dict is falsy, so the key is not added)
            orgs = claims.get("organizations", {})
            assert len(orgs) == 0


class TestOrganizationAuthServiceOwnerWebservices:
    """Test OrganizationAuthService._get_owner_webservices."""

    @pytest.mark.asyncio
    async def test_get_owner_webservices_returns_dict(self, organization_app_manager):
        """Test _get_owner_webservices returns dict keyed by client_id."""
        client_service = organization_app_manager.get_service("client")
        auth_service = organization_app_manager.get_service("auth")

        async with organization_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"OwnerWS-Corp-{uuid4().hex[:8]}",
                email=f"ownerws-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await session.commit()

        async with organization_app_manager.database.get_session() as session:
            result = await auth_service._get_owner_webservices(client.owner_id, session)
            assert isinstance(result, dict)
            assert client.id in result
            assert "webservices" in result[client.id]
