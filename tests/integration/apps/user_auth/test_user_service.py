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


# Shared fixture at module level to avoid SQLAlchemy registry pollution
@pytest_asyncio.fixture(scope="module")
async def user_auth_app_manager():
    """Create AppManager with user_auth app loaded (shared across all test classes in module)."""
    settings = LysAppSettings()
    settings.database.configure(
        type="sqlite",
        database=":memory:",
        echo=False
    )
    settings.apps = ["lys.apps.base", "lys.apps.user_auth"]

    app_manager = AppManager(settings=settings)
    app_manager.configure_component_types([
        AppComponentTypeEnum.ENTITIES,
        AppComponentTypeEnum.SERVICES,
    ])
    app_manager.load_all_components()
    await app_manager.database.initialize_database()

    # Create base test data (languages, genders, emailing types, etc.)
    language_service = app_manager.get_service("language")
    gender_service = app_manager.get_service("gender")
    emailing_type_service = app_manager.get_service("emailing_type")
    emailing_status_service = app_manager.get_service("emailing_status")
    one_time_token_type_service = app_manager.get_service("one_time_token_type")

    async with app_manager.database.get_session() as session:
        # Create test languages
        await language_service.create(session=session, id="en", enabled=True)
        await language_service.create(session=session, id="fr", enabled=True)

        # Create test genders
        await gender_service.create(session=session, id="M", enabled=True)
        await gender_service.create(session=session, id="F", enabled=True)

        # Create emailing types
        from lys.apps.user_auth.modules.emailing.consts import USER_PASSWORD_RESET_EMAILING_TYPE
        await emailing_type_service.create(
            session=session,
            id=USER_PASSWORD_RESET_EMAILING_TYPE,
            enabled=True,
            subject="Password Reset",
            template="password_reset",
            context_description={}
        )

        # Create emailing statuses
        await emailing_status_service.create(session=session, id="PENDING", enabled=True)
        await emailing_status_service.create(session=session, id="SENT", enabled=True)

        # Create one-time token types (duration in minutes)
        from lys.apps.base.modules.one_time_token.consts import PASSWORD_RESET_TOKEN_TYPE
        await one_time_token_type_service.create(
            session=session,
            id=PASSWORD_RESET_TOKEN_TYPE,
            enabled=True,
            duration=1440  # 24 hours
        )

    yield app_manager

    await app_manager.database.close()


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
