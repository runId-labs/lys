"""
Integration tests for LicensingAuthService.

Tests cover:
- generate_access_claims with subscription claims
- _get_subscription_claims for owned clients
- _get_client_subscription_claim with active plan
- Super user skips subscription claims
"""

import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from lys.apps.licensing.consts import FREE_PLAN, MAX_USERS, MAX_PROJECTS_PER_MONTH


class TestLicensingAuthServiceClaims:
    """Test LicensingAuthService.generate_access_claims."""

    @pytest.mark.asyncio
    async def test_generate_access_claims_with_subscription(self, licensing_app_manager):
        """Test claims include subscription data for client owner."""
        client_service = licensing_app_manager.get_service("client")
        auth_service = licensing_app_manager.get_service("auth")
        user_service = licensing_app_manager.get_service("user")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"LicAuth-Corp-{uuid4().hex[:8]}",
                email=f"licauth-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await session.commit()
            owner_id = client.owner_id

        async with licensing_app_manager.database.get_session() as session:
            owner = await user_service.get_by_id(owner_id, session)
            claims = await auth_service.generate_access_claims(owner, session)

            assert "subscriptions" in claims
            assert isinstance(claims["subscriptions"], dict)
            # Owner's client should have subscription data
            assert client.id in claims["subscriptions"]
            sub_claim = claims["subscriptions"][client.id]
            assert "plan_id" in sub_claim
            assert sub_claim["plan_id"] == FREE_PLAN

    @pytest.mark.asyncio
    async def test_generate_access_claims_super_user_skips_subscriptions(self, licensing_app_manager):
        """Test super user claims skip subscription resolution."""
        user_service = licensing_app_manager.get_service("user")
        auth_service = licensing_app_manager.get_service("auth")

        email = f"superlic-{uuid4().hex[:8]}@example.com"
        async with licensing_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=True,
                send_verification_email=False
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            assert claims["is_super_user"] is True
            # Super user should not have subscriptions resolved
            assert "subscriptions" not in claims or claims.get("subscriptions") is None


class TestLicensingAuthServiceSubscriptionClaims:
    """Test LicensingAuthService._get_subscription_claims."""

    @pytest.mark.asyncio
    async def test_get_subscription_claims_for_owner(self, licensing_app_manager):
        """Test subscription claims include plan rules."""
        client_service = licensing_app_manager.get_service("client")
        auth_service = licensing_app_manager.get_service("auth")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"SubClaims-Corp-{uuid4().hex[:8]}",
                email=f"subclaims-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await session.commit()
            owner_id = client.owner_id

        async with licensing_app_manager.database.get_session() as session:
            sub_claims = await auth_service._get_subscription_claims(owner_id, session)

            assert isinstance(sub_claims, dict)
            assert client.id in sub_claims
            claim = sub_claims[client.id]
            assert "rules" in claim
            # FREE plan has MAX_USERS=5 and MAX_PROJECTS_PER_MONTH=3
            assert MAX_USERS in claim["rules"]
            assert claim["rules"][MAX_USERS] == 5

    @pytest.mark.asyncio
    async def test_get_subscription_claims_no_client(self, licensing_app_manager):
        """Test subscription claims empty for user without clients."""
        user_service = licensing_app_manager.get_service("user")
        auth_service = licensing_app_manager.get_service("auth")

        email = f"noclient-{uuid4().hex[:8]}@example.com"
        async with licensing_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                send_verification_email=False,
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            sub_claims = await auth_service._get_subscription_claims(user.id, session)
            assert isinstance(sub_claims, dict)
            assert len(sub_claims) == 0


class TestLicensingAuthServiceClientSubscriptionClaim:
    """Test LicensingAuthService._get_client_subscription_claim."""

    @pytest.mark.asyncio
    async def test_get_client_subscription_claim_active(self, licensing_app_manager):
        """Test getting subscription claim for client with active subscription."""
        client_service = licensing_app_manager.get_service("client")
        auth_service = licensing_app_manager.get_service("auth")

        async with licensing_app_manager.database.get_session() as session:
            client = await client_service.create_client_with_owner(
                session=session,
                client_name=f"ClientSub-Corp-{uuid4().hex[:8]}",
                email=f"clientsub-{uuid4().hex[:8]}@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            await session.commit()

        async with licensing_app_manager.database.get_session() as session:
            claim = await auth_service._get_client_subscription_claim(client.id, session)

            assert claim is not None
            assert claim["plan_id"] == FREE_PLAN
            assert "plan_version_id" in claim
            assert "status" in claim
            assert "rules" in claim

    @pytest.mark.asyncio
    async def test_get_client_subscription_claim_no_subscription(self, licensing_app_manager):
        """Test getting subscription claim for client without subscription returns None."""
        auth_service = licensing_app_manager.get_service("auth")

        async with licensing_app_manager.database.get_session() as session:
            claim = await auth_service._get_client_subscription_claim(str(uuid4()), session)
            assert claim is None
