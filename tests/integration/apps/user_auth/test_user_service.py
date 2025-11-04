"""
Integration tests for UserService.

Tests cover:
- User CRUD operations (create, read, update)
- Password management (hashing, validation, reset)
- Email verification
- Status management
- GDPR anonymization
- Audit logging

Test approach: Real SQLite in-memory database with actual UserService operations.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.managers.app import AppManager
from lys.core.errors import LysError


# Note: user_auth_app_manager fixture is defined in conftest.py

class TestUserServiceCRUD:
    """Test UserService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user_with_valid_data(self, user_auth_app_manager):
        """Test creating a user with valid data."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            # Create user (language "en" created in fixture)
            user = await user_service.create_user(
                session=session,
                email="test@example.com",
                password="SecurePassword123!",
                language_id="en",
                send_verification_email=False,
                first_name="John",
                last_name="Doe"
            )

            assert user.id is not None
            assert user.email_address.id == "test@example.com"
            assert user.is_super_user is False
            assert user.language_id == "en"
            assert user.private_data.first_name == "John"
            assert user.private_data.last_name == "Doe"

    @pytest.mark.asyncio
    async def test_create_user_hashes_password(self, user_auth_app_manager):
        """Test that password is hashed when creating user."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            plain_password = "MyPassword123!"
            user = await user_service.create_user(
                session=session,
                email="hashtest@example.com",
                password=plain_password,
                language_id="en",
                send_verification_email=False
            )

            # Password should be hashed (not plain text)
            assert user.password != plain_password
            # Should start with bcrypt prefix
            assert user.password.startswith("$2b$")
            # Should be able to verify with check_password
            assert user_service.check_password(user, plain_password) is True

    @pytest.mark.asyncio
    async def test_create_user_with_duplicate_email_fails(self, user_auth_app_manager):
        """Test that creating user with duplicate email raises error."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            # Create first user
            await user_service.create_user(
                session=session,
                email="duplicate@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Try to create second user with same email
        async with user_auth_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.create_user(
                    session=session,
                    email="duplicate@example.com",
                    password="DifferentPassword123!",
                    language_id="en",
                    send_verification_email=False
                )

            assert "USER_ALREADY_EXISTS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_super_user(self, user_auth_app_manager):
        """Test creating a super user."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_super_user(
                session=session,
                email="admin@example.com",
                password="AdminPassword123!",
                language_id="en",
                send_verification_email=False
            )

            assert user.is_super_user is True
            assert user.email_address.id == "admin@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_returns_user(self, user_auth_app_manager):
        """Test getting user by email address."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            # Create user
            created_user = await user_service.create_user(
                session=session,
                email="findme@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Retrieve by email
        async with user_auth_app_manager.database.get_session() as session:
            found_user = await user_service.get_by_email("findme@example.com", session)

            assert found_user is not None
            assert found_user.id == created_user.id
            assert found_user.email_address.id == "findme@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_returns_none_for_nonexistent(self, user_auth_app_manager):
        """Test that get_by_email returns None for nonexistent email."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            found_user = await user_service.get_by_email("nonexistent@example.com", session)

            assert found_user is None

    @pytest.mark.asyncio
    async def test_update_user_basic_fields(self, user_auth_app_manager):
        """Test updating user private data fields."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            # Create user (language and gender created in fixture)
            user = await user_service.create_user(
                session=session,
                email="update@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False,
                first_name="John",
                last_name="Doe"
            )

            # Update user
            await user_service.update_user(
                user=user,
                first_name="Jane",
                last_name="Smith",
                gender_id="M",
                session=session
            )
            await session.flush()

            assert user.private_data.first_name == "Jane"
            assert user.private_data.last_name == "Smith"
            assert user.private_data.gender_id == "M"


class TestUserServicePasswordManagement:
    """Test UserService password management operations."""

    @pytest.mark.asyncio
    async def test_check_password_with_correct_password(self, user_auth_app_manager):
        """Test password verification with correct password."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            plain_password = "CorrectPassword123!"
            user = await user_service.create_user(
                session=session,
                email="pwcheck@example.com",
                password=plain_password,
                language_id="en",
                send_verification_email=False
            )

            # Verify password returns True for correct password
            assert user_service.check_password(user, plain_password) is True

    @pytest.mark.asyncio
    async def test_check_password_with_incorrect_password(self, user_auth_app_manager):
        """Test password verification with incorrect password."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="pwwrong@example.com",
                password="CorrectPassword123!",
                language_id="en",
                send_verification_email=False
            )

            # Verify password returns False for incorrect password
            assert user_service.check_password(user, "WrongPassword123!") is False

    @pytest.mark.asyncio
    async def test_update_password_hashes_new_password(self, user_auth_app_manager):
        """Test that update_password hashes the new password."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            old_password = "OldPassword123!"
            new_password = "NewPassword456!"

            user = await user_service.create_user(
                session=session,
                email="pwupdate@example.com",
                password=old_password,
                language_id="en",
                send_verification_email=False
            )

            old_hashed = user.password

            # Update password
            await user_service.update_password(
                user=user,
                current_password=old_password,
                new_password=new_password,
                session=session
            )
            await session.flush()

            # New password should be hashed and different from old
            assert user.password != old_hashed
            assert user.password != new_password
            assert user.password.startswith("$2b$")
            # Old password should no longer work
            assert user_service.check_password(user, old_password) is False
            # New password should work
            assert user_service.check_password(user, new_password) is True

    @pytest.mark.asyncio
    async def test_update_password_validates_old_password(self, user_auth_app_manager):
        """Test that update_password validates current password."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="pwvalidate@example.com",
                password="CorrectPassword123!",
                language_id="en",
                send_verification_email=False
            )

            # Try to update with wrong current password
            with pytest.raises(LysError) as exc_info:
                await user_service.update_password(
                    user=user,
                    current_password="WrongPassword123!",
                    new_password="NewPassword456!",
                    session=session
                )

            assert "WRONG_CREDENTIALS" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_password_reset_creates_token(self, user_auth_app_manager):
        """Test that request_password_reset creates one-time token."""
        user_service = user_auth_app_manager.get_service("user")
        token_service = user_auth_app_manager.get_service("user_one_time_token")

        async with user_auth_app_manager.database.get_session() as session:
            # Create user
            user = await user_service.create_user(
                session=session,
                email="pwreset@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Request password reset (without background_tasks)
        async with user_auth_app_manager.database.get_session() as session:
            result = await user_service.request_password_reset(
                email="pwreset@example.com",
                session=session,
                background_tasks=None
            )

            assert result is True

            # Verify token was created
            from sqlalchemy import select
            from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

            token_entity = user_auth_app_manager.get_entity("user_one_time_token")
            stmt = select(token_entity).where(
                token_entity.user_id == user.id,
                token_entity.type_id == PASSWORD_RESET_TOKEN_TYPE
            )
            result = await session.execute(stmt)
            token = result.scalar_one_or_none()

            assert token is not None
            assert token.user_id == user.id
            assert token.type_id == PASSWORD_RESET_TOKEN_TYPE

    @pytest.mark.asyncio
    async def test_reset_password_with_valid_token(self, user_auth_app_manager):
        """Test password reset with valid token."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            # Create user
            user = await user_service.create_user(
                session=session,
                email="pwresetvalid@example.com",
                password="OldPassword123!",
                language_id="en",
                send_verification_email=False
            )

        # Request password reset
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.request_password_reset(
                email="pwresetvalid@example.com",
                session=session,
                background_tasks=None
            )

            # Get the token
            from sqlalchemy import select
            from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

            token_entity = user_auth_app_manager.get_entity("user_one_time_token")
            stmt = select(token_entity).where(
                token_entity.user_id == user.id,
                token_entity.type_id == PASSWORD_RESET_TOKEN_TYPE
            )
            result = await session.execute(stmt)
            token = result.scalar_one()

        # Reset password with token
        async with user_auth_app_manager.database.get_session() as session:
            new_password = "NewPassword456!"
            updated_user = await user_service.reset_password(
                token=str(token.id),
                new_password=new_password,
                session=session
            )

            # Verify new password works
            assert user_service.check_password(updated_user, new_password) is True
            # Verify old password doesn't work
            assert user_service.check_password(updated_user, "OldPassword123!") is False

    @pytest.mark.asyncio
    async def test_reset_password_with_used_token_fails(self, user_auth_app_manager):
        """Test that reset password fails with already used token."""
        user_service = user_auth_app_manager.get_service("user")

        async with user_auth_app_manager.database.get_session() as session:
            # Create user
            user = await user_service.create_user(
                session=session,
                email="pwresetused@example.com",
                password="OldPassword123!",
                language_id="en",
                send_verification_email=False
            )

        # Request password reset
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.request_password_reset(
                email="pwresetused@example.com",
                session=session,
                background_tasks=None
            )

            # Get the token
            from sqlalchemy import select
            from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE

            token_entity = user_auth_app_manager.get_entity("user_one_time_token")
            stmt = select(token_entity).where(
                token_entity.user_id == user.id,
                token_entity.type_id == PASSWORD_RESET_TOKEN_TYPE
            )
            result = await session.execute(stmt)
            token = result.scalar_one()

        # Use token once
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.reset_password(
                token=str(token.id),
                new_password="NewPassword456!",
                session=session
            )

        # Try to use token again
        async with user_auth_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.reset_password(
                    token=str(token.id),
                    new_password="AnotherPassword789!",
                    session=session
                )

            # Token has been used, so it should be invalid
            assert "INVALID_RESET_TOKEN_ERROR" in str(exc_info.value) or "TOKEN_ALREADY_USED" in str(exc_info.value)


class TestUserServiceEmailVerification:
    """Tests for UserService email verification methods."""

    @pytest.mark.asyncio
    async def test_verify_email_with_valid_token(self, user_auth_app_manager):
        """Test that email can be verified with valid token."""
        user_service = user_auth_app_manager.get_service("user")
        token_service = user_auth_app_manager.get_service("user_one_time_token")

        # Create user (email not verified by default)
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="emailverify@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            # Verify email is not validated
            assert user.email_address.validated_at is None

        # Create email verification token
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=EMAIL_VERIFICATION_TOKEN_TYPE
            )

        # Verify email with token
        async with user_auth_app_manager.database.get_session() as session:
            verified_user = await user_service.verify_email(
                token=str(token.id),
                session=session
            )

            # Verify email is now validated
            assert verified_user.email_address.validated_at is not None
            assert verified_user.id == user.id

    @pytest.mark.asyncio
    async def test_verify_email_with_expired_token_fails(self, user_auth_app_manager):
        """Test that email verification fails with expired token."""
        user_service = user_auth_app_manager.get_service("user")
        token_service = user_auth_app_manager.get_service("user_one_time_token")

        # Create user
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="expiredtoken@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create email verification token and make it expired
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE
            from datetime import timedelta
            from lys.core.utils.datetime import now_utc

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=EMAIL_VERIFICATION_TOKEN_TYPE
            )

            # Make token expired (email verification tokens are valid for 1440 minutes / 24 hours)
            # Set created_at to 1441 minutes ago
            token.created_at = now_utc() - timedelta(minutes=1441)
            await session.flush()

        # Try to verify email with expired token
        async with user_auth_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.verify_email(
                    token=str(token.id),
                    session=session
                )

            # Should raise EXPIRED_RESET_TOKEN_ERROR
            assert "EXPIRED_RESET_TOKEN_ERROR" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_email_with_used_token_fails(self, user_auth_app_manager):
        """Test that email verification fails with already used token."""
        user_service = user_auth_app_manager.get_service("user")
        token_service = user_auth_app_manager.get_service("user_one_time_token")

        # Create user
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="usedtoken@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create email verification token
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

            token = await token_service.create(
                session,
                user_id=user.id,
                type_id=EMAIL_VERIFICATION_TOKEN_TYPE
            )

        # Use token once
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.verify_email(
                token=str(token.id),
                session=session
            )

        # Try to use token again
        async with user_auth_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.verify_email(
                    token=str(token.id),
                    session=session
                )

            # Token has been used, so it should be invalid
            assert "INVALID_RESET_TOKEN_ERROR" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_email_with_already_verified_email_fails(self, user_auth_app_manager):
        """Test that email verification fails if email is already verified."""
        user_service = user_auth_app_manager.get_service("user")
        token_service = user_auth_app_manager.get_service("user_one_time_token")

        # Create user
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service.create_user(
                session=session,
                email="alreadyverified@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create and use first token to verify email
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

            token1 = await token_service.create(
                session,
                user_id=user.id,
                type_id=EMAIL_VERIFICATION_TOKEN_TYPE
            )

        async with user_auth_app_manager.database.get_session() as session:
            await user_service.verify_email(
                token=str(token1.id),
                session=session
            )

        # Create second token for already verified email
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.base.modules.one_time_token.consts import EMAIL_VERIFICATION_TOKEN_TYPE

            token2 = await token_service.create(
                session,
                user_id=user.id,
                type_id=EMAIL_VERIFICATION_TOKEN_TYPE
            )

        # Try to verify again with second token
        async with user_auth_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.verify_email(
                    token=str(token2.id),
                    session=session
                )

            # Should raise EMAIL_ALREADY_VALIDATED_ERROR
            assert "EMAIL_ALREADY_VALIDATED_ERROR" in str(exc_info.value)


class TestUserServiceStatusManagement:
    """Tests for UserService status management methods."""

    @pytest.mark.asyncio
    async def test_update_status_changes_status_and_creates_audit_log(self, user_auth_app_manager):
        """Test that update_status changes user status and creates audit log."""
        user_service = user_auth_app_manager.get_service("user")
        user_audit_log_service = user_auth_app_manager.get_service("user_audit_log")

        # Create two users: target user and admin user
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="status_target@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="status_admin@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            # Default status should be ENABLED
            from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS
            assert target_user.status_id == ENABLED_USER_STATUS

        # Update status to DISABLED
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import DISABLED_USER_STATUS

            # Get fresh user instance
            user = await user_service.get_by_id(target_user.id, session)

            updated_user = await user_service.update_status(
                user=user,
                status_id=DISABLED_USER_STATUS,
                reason="User requested account suspension",
                author_user_id=admin_user.id,
                session=session
            )

            # Verify status changed
            assert updated_user.status_id == DISABLED_USER_STATUS

            # Verify audit log was created
            from sqlalchemy import select
            user_audit_log_entity = user_auth_app_manager.get_entity("user_audit_log")
            stmt = select(user_audit_log_entity).where(
                user_audit_log_entity.target_user_id == target_user.id
            )
            result = await session.execute(stmt)
            audit_logs = result.scalars().all()

            assert len(audit_logs) == 1
            audit_log = audit_logs[0]
            assert audit_log.author_user_id == admin_user.id
            assert audit_log.target_user_id == target_user.id
            assert "ENABLED → DISABLED" in audit_log.message
            assert "User requested account suspension" in audit_log.message

    @pytest.mark.asyncio
    async def test_update_status_prevents_deleted_status(self, user_auth_app_manager):
        """Test that update_status prevents setting DELETED status directly."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="status_target2@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="status_admin2@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Try to update status to DELETED (should fail)
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import DELETED_USER_STATUS

            # Get fresh user instance
            user = await user_service.get_by_id(target_user.id, session)

            with pytest.raises(LysError) as exc_info:
                await user_service.update_status(
                    user=user,
                    status_id=DELETED_USER_STATUS,
                    reason="Test deletion",
                    author_user_id=admin_user.id,
                    session=session
                )

            # Should raise INVALID_STATUS_CHANGE
            assert "INVALID_STATUS_CHANGE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_status_with_invalid_status_fails(self, user_auth_app_manager):
        """Test that update_status fails with invalid status_id."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="status_target3@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="status_admin3@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Try to update status to invalid status
        async with user_auth_app_manager.database.get_session() as session:
            # Get fresh user instance
            user = await user_service.get_by_id(target_user.id, session)

            with pytest.raises(LysError) as exc_info:
                await user_service.update_status(
                    user=user,
                    status_id="INVALID_STATUS",
                    reason="Test invalid status",
                    author_user_id=admin_user.id,
                    session=session
                )

            # Should raise INVALID_USER_STATUS
            assert "INVALID_USER_STATUS" in str(exc_info.value)


class TestUserServiceGDPRAnonymization:
    """Tests for UserService GDPR anonymization methods."""

    @pytest.mark.asyncio
    async def test_anonymize_user_removes_personal_data(self, user_auth_app_manager):
        """Test that anonymize_user removes all personal data."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users with private data
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="gdpr_target@example.com",
                password="Password123!",
                language_id="en",
                first_name="John",
                last_name="Doe",
                gender_id="M",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="gdpr_admin@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

            # Verify initial data exists
            assert target_user.private_data is not None
            assert target_user.private_data.first_name == "John"
            assert target_user.private_data.last_name == "Doe"
            assert target_user.private_data.gender_id == "M"
            assert target_user.private_data.anonymized_at is None

        # Anonymize user
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.anonymize_user(
                user_id=target_user.id,
                reason="User requested account deletion",
                anonymized_by=admin_user.id,
                session=session
            )

        # Verify data was anonymized
        async with user_auth_app_manager.database.get_session() as session:
            anonymized_user = await user_service.get_by_id(target_user.id, session)

            # Personal data should be removed
            assert anonymized_user.private_data.first_name is None
            assert anonymized_user.private_data.last_name is None
            assert anonymized_user.private_data.gender_id is None
            assert anonymized_user.private_data.anonymized_at is not None

            # Status should be DELETED
            from lys.apps.user_auth.modules.user.consts import DELETED_USER_STATUS
            assert anonymized_user.status_id == DELETED_USER_STATUS

    @pytest.mark.asyncio
    async def test_anonymize_user_preserves_audit_trails(self, user_auth_app_manager):
        """Test that anonymize_user preserves user_id and email, and creates audit log."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="gdpr_audit@example.com",
                password="Password123!",
                language_id="en",
                first_name="Jane",
                last_name="Smith",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="gdpr_admin2@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Anonymize user
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.anonymize_user(
                user_id=target_user.id,
                reason="GDPR compliance request",
                anonymized_by=admin_user.id,
                session=session
            )

        # Verify audit trail is preserved
        async with user_auth_app_manager.database.get_session() as session:
            anonymized_user = await user_service.get_by_id(target_user.id, session)

            # User ID and email should be preserved for audit/legal purposes
            assert anonymized_user.id == target_user.id
            assert anonymized_user.email_address.address == "gdpr_audit@example.com"

            # Audit log should be created
            from sqlalchemy import select
            user_audit_log_entity = user_auth_app_manager.get_entity("user_audit_log")
            from lys.apps.user_auth.modules.user.consts import ANONYMIZATION_LOG_TYPE

            stmt = select(user_audit_log_entity).where(
                user_audit_log_entity.target_user_id == target_user.id,
                user_audit_log_entity.log_type_id == ANONYMIZATION_LOG_TYPE
            )
            result = await session.execute(stmt)
            audit_logs = result.scalars().all()

            assert len(audit_logs) == 1
            audit_log = audit_logs[0]
            assert audit_log.author_user_id == admin_user.id
            assert "GDPR compliance request" in audit_log.message
            assert "DELETED (anonymized)" in audit_log.message

    @pytest.mark.asyncio
    async def test_anonymize_user_already_anonymized_fails(self, user_auth_app_manager):
        """Test that anonymizing an already anonymized user fails."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="gdpr_double@example.com",
                password="Password123!",
                language_id="en",
                first_name="Bob",
                last_name="Johnson",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="gdpr_admin3@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Anonymize user first time
        async with user_auth_app_manager.database.get_session() as session:
            await user_service.anonymize_user(
                user_id=target_user.id,
                reason="First anonymization",
                anonymized_by=admin_user.id,
                session=session
            )

        # Try to anonymize again (should fail)
        async with user_auth_app_manager.database.get_session() as session:
            with pytest.raises(LysError) as exc_info:
                await user_service.anonymize_user(
                    user_id=target_user.id,
                    reason="Second anonymization attempt",
                    anonymized_by=admin_user.id,
                    session=session
                )

            # Should raise USER_ALREADY_ANONYMIZED
            assert "USER_ALREADY_ANONYMIZED" in str(exc_info.value)


class TestUserServiceAuditLogging:
    """Tests for UserService audit logging functionality."""

    @pytest.mark.asyncio
    async def test_create_manual_observation(self, user_auth_app_manager):
        """Test creating a manual observation audit log."""
        user_service = user_auth_app_manager.get_service("user")
        audit_log_service = user_auth_app_manager.get_service("user_audit_log")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="audit_target@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="audit_admin@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create manual observation
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import OBSERVATION_LOG_TYPE

            audit_log = await audit_log_service.create_audit_log(
                target_user_id=target_user.id,
                author_user_id=admin_user.id,
                log_type_id=OBSERVATION_LOG_TYPE,
                message="User contacted support regarding billing issue",
                session=session
            )

            # Verify audit log was created
            assert audit_log.target_user_id == target_user.id
            assert audit_log.author_user_id == admin_user.id
            assert audit_log.log_type_id == OBSERVATION_LOG_TYPE
            assert "billing issue" in audit_log.message
            assert audit_log.deleted_at is None

    @pytest.mark.asyncio
    async def test_update_observation_updates_message(self, user_auth_app_manager):
        """Test updating an observation audit log message."""
        user_service = user_auth_app_manager.get_service("user")
        audit_log_service = user_auth_app_manager.get_service("user_audit_log")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="audit_update@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="audit_admin2@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create observation
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import OBSERVATION_LOG_TYPE

            audit_log = await audit_log_service.create_audit_log(
                target_user_id=target_user.id,
                author_user_id=admin_user.id,
                log_type_id=OBSERVATION_LOG_TYPE,
                message="Original observation",
                session=session
            )

        # Update observation
        async with user_auth_app_manager.database.get_session() as session:
            # Get fresh audit log instance
            log = await audit_log_service.get_by_id(audit_log.id, session)

            updated_log = await audit_log_service.update_observation(
                log=log,
                new_message="Updated observation with more details",
                session=session
            )

            # Verify message was updated
            assert updated_log.message == "Updated observation with more details"
            assert updated_log.id == audit_log.id

    @pytest.mark.asyncio
    async def test_update_observation_fails_for_system_logs(self, user_auth_app_manager):
        """Test that updating system logs (STATUS_CHANGE, ANONYMIZATION) fails."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="audit_system@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="audit_admin3@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create a status change (system log)
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import DISABLED_USER_STATUS

            user = await user_service.get_by_id(target_user.id, session)
            await user_service.update_status(
                user=user,
                status_id=DISABLED_USER_STATUS,
                reason="Account suspended",
                author_user_id=admin_user.id,
                session=session
            )

        # Try to update system log (should fail)
        async with user_auth_app_manager.database.get_session() as session:
            audit_log_service = user_auth_app_manager.get_service("user_audit_log")
            from sqlalchemy import select
            user_audit_log_entity = user_auth_app_manager.get_entity("user_audit_log")
            from lys.apps.user_auth.modules.user.consts import STATUS_CHANGE_LOG_TYPE

            stmt = select(user_audit_log_entity).where(
                user_audit_log_entity.target_user_id == target_user.id,
                user_audit_log_entity.log_type_id == STATUS_CHANGE_LOG_TYPE
            )
            result = await session.execute(stmt)
            system_log = result.scalar_one()

            with pytest.raises(LysError) as exc_info:
                await audit_log_service.update_observation(
                    log=system_log,
                    new_message="Trying to modify system log",
                    session=session
                )

            # Should raise CANNOT_EDIT_SYSTEM_LOG
            assert "CANNOT_EDIT_SYSTEM_LOG" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_observation_soft_deletes_log(self, user_auth_app_manager):
        """Test soft deleting an observation audit log."""
        user_service = user_auth_app_manager.get_service("user")
        audit_log_service = user_auth_app_manager.get_service("user_audit_log")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="audit_delete@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="audit_admin4@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create observation
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import OBSERVATION_LOG_TYPE

            audit_log = await audit_log_service.create_audit_log(
                target_user_id=target_user.id,
                author_user_id=admin_user.id,
                log_type_id=OBSERVATION_LOG_TYPE,
                message="Observation to be deleted",
                session=session
            )
            assert audit_log.deleted_at is None

        # Delete observation
        async with user_auth_app_manager.database.get_session() as session:
            log = await audit_log_service.get_by_id(audit_log.id, session)

            deleted_log = await audit_log_service.delete_observation(
                log=log,
                session=session
            )

            # Verify soft delete
            assert deleted_log.deleted_at is not None
            assert deleted_log.id == audit_log.id

    @pytest.mark.asyncio
    async def test_delete_observation_fails_for_system_logs(self, user_auth_app_manager):
        """Test that deleting system logs fails."""
        user_service = user_auth_app_manager.get_service("user")

        # Create users
        async with user_auth_app_manager.database.get_session() as session:
            target_user = await user_service.create_user(
                session=session,
                email="audit_delsys@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )
            admin_user = await user_service.create_user(
                session=session,
                email="audit_admin5@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Create a status change (system log)
        async with user_auth_app_manager.database.get_session() as session:
            from lys.apps.user_auth.modules.user.consts import DISABLED_USER_STATUS

            user = await user_service.get_by_id(target_user.id, session)
            await user_service.update_status(
                user=user,
                status_id=DISABLED_USER_STATUS,
                reason="Account suspended",
                author_user_id=admin_user.id,
                session=session
            )

        # Try to delete system log (should fail)
        async with user_auth_app_manager.database.get_session() as session:
            audit_log_service = user_auth_app_manager.get_service("user_audit_log")
            from sqlalchemy import select
            user_audit_log_entity = user_auth_app_manager.get_entity("user_audit_log")
            from lys.apps.user_auth.modules.user.consts import STATUS_CHANGE_LOG_TYPE

            stmt = select(user_audit_log_entity).where(
                user_audit_log_entity.target_user_id == target_user.id,
                user_audit_log_entity.log_type_id == STATUS_CHANGE_LOG_TYPE
            )
            result = await session.execute(stmt)
            system_log = result.scalar_one()

            with pytest.raises(LysError) as exc_info:
                await audit_log_service.delete_observation(
                    log=system_log,
                    session=session
                )

            # Should raise CANNOT_DELETE_SYSTEM_LOG
            assert "CANNOT_DELETE_SYSTEM_LOG" in str(exc_info.value)


