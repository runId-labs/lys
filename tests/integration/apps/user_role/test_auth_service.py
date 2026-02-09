"""
Integration tests for RoleAuthService.

Tests cover:
- generate_access_claims with roles
- _get_user_role_webservices
- Super user skips role webservices
"""

import pytest
from uuid import uuid4


class TestRoleAuthServiceClaims:
    """Test RoleAuthService.generate_access_claims."""

    @pytest.mark.asyncio
    async def test_generate_access_claims_with_roles(self, user_role_app_manager):
        """Test claims include role-based webservices for user with roles."""
        user_service = user_role_app_manager.get_service("user")
        auth_service = user_role_app_manager.get_service("auth")

        email = f"roleclaims-{uuid4().hex[:8]}@example.com"
        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                send_verification_email=False,
                roles=["ROLE_A"]
            )
            await session.commit()

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            assert "sub" in claims
            assert claims["sub"] == str(user.id)
            assert "webservices" in claims
            # ROLE_A has webservice "ws_a" per conftest
            assert "ws_a" in claims["webservices"]
            assert claims["webservices"]["ws_a"] == "full"

    @pytest.mark.asyncio
    async def test_generate_access_claims_multiple_roles(self, user_role_app_manager):
        """Test claims include webservices from multiple roles."""
        user_service = user_role_app_manager.get_service("user")
        auth_service = user_role_app_manager.get_service("auth")

        email = f"multirole-{uuid4().hex[:8]}@example.com"
        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                send_verification_email=False,
                roles=["ROLE_A", "ROLE_B"]
            )
            await session.commit()

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            assert "ws_a" in claims["webservices"]
            assert "ws_b" in claims["webservices"]

    @pytest.mark.asyncio
    async def test_generate_access_claims_super_user_skips_roles(self, user_role_app_manager):
        """Test that super user claims skip role webservices."""
        user_service = user_role_app_manager.get_service("user")
        auth_service = user_role_app_manager.get_service("auth")

        email = f"superrole-{uuid4().hex[:8]}@example.com"
        async with user_role_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=True,
                send_verification_email=False
            )
            await session.commit()

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            assert claims["is_super_user"] is True
            # Super user does not need explicit role webservices
            # (permission layer grants all access)

    @pytest.mark.asyncio
    async def test_generate_access_claims_no_roles(self, user_role_app_manager):
        """Test claims for user without any roles."""
        user_service = user_role_app_manager.get_service("user")
        auth_service = user_role_app_manager.get_service("auth")

        email = f"norole-{uuid4().hex[:8]}@example.com"
        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                send_verification_email=False,
            )
            await session.commit()

        async with user_role_app_manager.database.get_session() as session:
            user = await user_service.get_by_id(user.id, session)
            claims = await auth_service.generate_access_claims(user, session)

            assert claims["is_super_user"] is False
            # Should not have role-specific webservices ws_a or ws_b
            assert "ws_a" not in claims["webservices"]
            assert "ws_b" not in claims["webservices"]
