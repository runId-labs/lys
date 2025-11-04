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


class TestUserServiceCRUD:
    """Test UserService CRUD operations."""

    @pytest_asyncio.fixture(scope="class")
    async def app_manager(self):
        """Create AppManager with user_auth app loaded (shared across all tests in class)."""
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

        # Create base test data (languages, genders, etc.)
        language_service = app_manager.get_service("language")
        gender_service = app_manager.get_service("gender")

        async with app_manager.database.get_session() as session:
            # Create test languages
            await language_service.create(session=session, id="en", enabled=True)
            await language_service.create(session=session, id="fr", enabled=True)

            # Create test genders
            await gender_service.create(session=session, id="M", enabled=True)
            await gender_service.create(session=session, id="F", enabled=True)

        yield app_manager

        await app_manager.database.close()

    @pytest.mark.asyncio
    async def test_create_user_with_valid_data(self, app_manager):
        """Test creating a user with valid data."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
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
    async def test_create_user_hashes_password(self, app_manager):
        """Test that password is hashed when creating user."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
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
    async def test_create_user_with_duplicate_email_fails(self, app_manager):
        """Test that creating user with duplicate email raises error."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
            # Create first user
            await user_service.create_user(
                session=session,
                email="duplicate@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Try to create second user with same email
        async with app_manager.database.get_session() as session:
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
    async def test_create_super_user(self, app_manager):
        """Test creating a super user."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
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
    async def test_get_by_email_returns_user(self, app_manager):
        """Test getting user by email address."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
            # Create user
            created_user = await user_service.create_user(
                session=session,
                email="findme@example.com",
                password="Password123!",
                language_id="en",
                send_verification_email=False
            )

        # Retrieve by email
        async with app_manager.database.get_session() as session:
            found_user = await user_service.get_by_email("findme@example.com", session)

            assert found_user is not None
            assert found_user.id == created_user.id
            assert found_user.email_address.id == "findme@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_returns_none_for_nonexistent(self, app_manager):
        """Test that get_by_email returns None for nonexistent email."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
            found_user = await user_service.get_by_email("nonexistent@example.com", session)

            assert found_user is None

    @pytest.mark.asyncio
    async def test_update_user_basic_fields(self, app_manager):
        """Test updating user private data fields."""
        user_service = app_manager.get_service("user")

        async with app_manager.database.get_session() as session:
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
