"""
Integration tests for OneTimeTokenService.

Tests cover:
- get_valid_token (valid, expired, used)
- mark_as_used
- revoke_token
- use_token
"""

import pytest
from uuid import uuid4

from lys.apps.base.modules.one_time_token.consts import (
    PENDING_TOKEN_STATUS, USED_TOKEN_STATUS, REVOKED_TOKEN_STATUS,
    PASSWORD_RESET_TOKEN_TYPE,
)


class TestOneTimeTokenServiceGetValidToken:
    """Test OneTimeTokenService.get_valid_token."""

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_pending(self, user_auth_app_manager):
        """Test get_valid_token returns a pending, non-expired token."""
        token_service = user_auth_app_manager.get_service("user_one_time_token")
        user_service = user_auth_app_manager.get_service("user")

        email = f"token-{uuid4().hex[:8]}@example.com"
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=PASSWORD_RESET_TOKEN_TYPE,
                status_id=PENDING_TOKEN_STATUS
            )
            await session.commit()

            valid = await token_service.get_valid_token(token.id, session)
            assert valid is not None
            assert valid.id == token.id

    @pytest.mark.asyncio
    async def test_get_valid_token_used_returns_none(self, user_auth_app_manager):
        """Test get_valid_token returns None for a used token."""
        token_service = user_auth_app_manager.get_service("user_one_time_token")
        user_service = user_auth_app_manager.get_service("user")

        email = f"token-used-{uuid4().hex[:8]}@example.com"
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=PASSWORD_RESET_TOKEN_TYPE,
                status_id=PENDING_TOKEN_STATUS
            )
            await token_service.mark_as_used(token, session)
            await session.commit()

            valid = await token_service.get_valid_token(token.id, session)
            assert valid is None


class TestOneTimeTokenServiceMarkAsUsed:
    """Test OneTimeTokenService.mark_as_used."""

    @pytest.mark.asyncio
    async def test_mark_as_used(self, user_auth_app_manager):
        """Test marking a token as used updates status and used_at."""
        token_service = user_auth_app_manager.get_service("user_one_time_token")
        user_service = user_auth_app_manager.get_service("user")

        email = f"token-mark-{uuid4().hex[:8]}@example.com"
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=PASSWORD_RESET_TOKEN_TYPE,
                status_id=PENDING_TOKEN_STATUS
            )
            await session.commit()

            await token_service.mark_as_used(token, session)
            await session.commit()

            assert token.status_id == USED_TOKEN_STATUS
            assert token.used_at is not None


class TestOneTimeTokenServiceRevoke:
    """Test OneTimeTokenService.revoke_token."""

    @pytest.mark.asyncio
    async def test_revoke_token(self, user_auth_app_manager):
        """Test revoking a token sets status to REVOKED."""
        token_service = user_auth_app_manager.get_service("user_one_time_token")
        user_service = user_auth_app_manager.get_service("user")

        email = f"token-rev-{uuid4().hex[:8]}@example.com"
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=PASSWORD_RESET_TOKEN_TYPE,
                status_id=PENDING_TOKEN_STATUS
            )
            await session.commit()

            await token_service.revoke_token(token, session)
            await session.commit()

            assert token.status_id == REVOKED_TOKEN_STATUS


class TestOneTimeTokenServiceUseToken:
    """Test OneTimeTokenService.use_token."""

    @pytest.mark.asyncio
    async def test_use_token_valid(self, user_auth_app_manager):
        """Test use_token marks valid token as used."""
        token_service = user_auth_app_manager.get_service("user_one_time_token")
        user_service = user_auth_app_manager.get_service("user")

        email = f"token-use-{uuid4().hex[:8]}@example.com"
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=PASSWORD_RESET_TOKEN_TYPE,
                status_id=PENDING_TOKEN_STATUS
            )
            await session.commit()
            token_id = token.id

        async with user_auth_app_manager.database.get_session() as session:
            used = await token_service.use_token(token_id, session)
            assert used is not None
            assert used.status_id == USED_TOKEN_STATUS

    @pytest.mark.asyncio
    async def test_use_token_nonexistent_returns_none(self, user_auth_app_manager):
        """Test use_token returns None for nonexistent token."""
        token_service = user_auth_app_manager.get_service("user_one_time_token")

        async with user_auth_app_manager.database.get_session() as session:
            result = await token_service.use_token(str(uuid4()), session)
            assert result is None
