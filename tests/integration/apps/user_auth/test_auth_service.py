"""
Integration tests for AuthService.

Tests cover:
- Phase 2.7: User lookup by login (3 tests)
- Phase 2.8: Login attempt tracking (3 tests)
- Phase 2.9: Rate limiting logic (6 tests)
- Phase 2.10: Authentication flow (7 tests)
"""
import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
from sqlalchemy import select
from starlette.responses import Response

from lys.apps.user_auth.consts import REFRESH_COOKIE_KEY, ACCESS_COOKIE_KEY
from lys.apps.user_auth.errors import (
    INVALID_CREDENTIALS_ERROR,
    RATE_LIMIT_ERROR
)
from lys.apps.user_auth.modules.auth.consts import (
    FAILED_LOGIN_ATTEMPT_STATUS,
    SUCCEED_LOGIN_ATTEMPT_STATUS
)
from lys.apps.user_auth.modules.auth.models import LoginInputModel
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS, DISABLED_USER_STATUS
from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.errors import LysError
from lys.core.managers.app import AppManager
from lys.core.utils.datetime import now_utc


# Note: This module uses the user_auth_app_manager fixture from test_user_service.py
# The fixture is imported via pytest's fixture discovery mechanism


def unique_email():
    """Generate a unique email for each test."""
    return f"test-{uuid4().hex[:8]}@example.com"


# Default auth config for tests that need token generation
_TEST_AUTH_CONFIG = {
    "connection_expire_minutes": 60,
    "once_refresh_token_expire_minutes": 30,
    "access_token_expire_minutes": 15,
    "encryption_algorithm": "HS256",
    "cookie_secure": False,
    "cookie_http_only": True,
    "cookie_same_site": "lax",
    "cookie_domain": None,
    "login_rate_limit_enabled": True,
    "login_lockout_durations": {3: 60, 5: 900},
}

_TEST_SECRET_KEY = "test-secret-key-for-jwt-testing-12345"


# ==============================================================================
# Phase 2.7: User Lookup by Login (3 tests)
# ==============================================================================


class TestAuthServiceUserLookup:
    """Tests for AuthService user lookup methods."""

    @pytest.mark.asyncio
    async def test_get_user_from_login_by_email(self, user_auth_app_manager):
        """Test getting user by email address."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Lookup user by email
            found_user = await auth_service.get_user_from_login(email, session)

            assert found_user is not None
            assert found_user.id == user.id
            assert found_user.email_address.address == email

    @pytest.mark.asyncio
    async def test_get_user_from_login_not_found(self, user_auth_app_manager):
        """Test getting user with non-existent login returns None."""
        auth_service = user_auth_app_manager.get_service("auth")

        async with user_auth_app_manager.database.get_session() as session:
            found_user = await auth_service.get_user_from_login("nonexistent@example.com", session)
            assert found_user is None

    @pytest.mark.asyncio
    async def test_get_user_from_login_case_sensitive(self, user_auth_app_manager):
        """Test that email lookup is case-sensitive."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = "lowercase@example.com"

        async with user_auth_app_manager.database.get_session() as session:
            # Create user with lowercase email
            await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Try lookup with different case
            found_user = await auth_service.get_user_from_login("LOWERCASE@example.com", session)

            # Should not find user (email is case-sensitive)
            assert found_user is None


# ==============================================================================
# Phase 2.8: Login Attempt Tracking (3 tests)
# ==============================================================================


class TestAuthServiceLoginAttemptTracking:
    """Tests for AuthService login attempt tracking."""

    @pytest.mark.asyncio
    async def test_get_user_last_login_attempt_success(self, user_auth_app_manager):
        """Test getting last login attempt for user."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        user_login_attempt_entity = user_auth_app_manager.get_entity("user_login_attempt")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Create login attempt
            attempt = user_login_attempt_entity(
                status_id=FAILED_LOGIN_ATTEMPT_STATUS,
                user_id=user.id,
                attempt_count=1,
                blocked_until=None
            )
            session.add(attempt)
            await session.commit()

            # Get last login attempt
            last_attempt = await auth_service.get_user_last_login_attempt(user, session)

            assert last_attempt is not None
            assert last_attempt.user_id == user.id
            assert last_attempt.status_id == FAILED_LOGIN_ATTEMPT_STATUS
            assert last_attempt.attempt_count == 1

    @pytest.mark.asyncio
    async def test_get_user_last_login_attempt_no_attempts(self, user_auth_app_manager):
        """Test getting last login attempt when user has no attempts."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user without any login attempts
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Get last login attempt
            last_attempt = await auth_service.get_user_last_login_attempt(user, session)

            assert last_attempt is None

    @pytest.mark.asyncio
    async def test_get_user_last_login_attempt_multiple_attempts(self, user_auth_app_manager):
        """Test getting last login attempt when multiple attempts exist."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        user_login_attempt_entity = user_auth_app_manager.get_entity("user_login_attempt")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Create multiple login attempts
            for i in range(3):
                attempt = user_login_attempt_entity(
                    status_id=FAILED_LOGIN_ATTEMPT_STATUS if i < 2 else SUCCEED_LOGIN_ATTEMPT_STATUS,
                    user_id=user.id,
                    attempt_count=i + 1,
                    blocked_until=None
                )
                session.add(attempt)
                await session.commit()
                if i < 2:
                    await asyncio.sleep(0.1)  # Delay between attempts

            # Get last login attempt
            last_attempt = await auth_service.get_user_last_login_attempt(user, session)

            # Should return one of the attempts (order by created_at desc)
            assert last_attempt is not None
            assert last_attempt.user_id == user.id
            # Verify it's a valid login attempt with expected fields
            assert last_attempt.status_id in [FAILED_LOGIN_ATTEMPT_STATUS, SUCCEED_LOGIN_ATTEMPT_STATUS]
            assert last_attempt.attempt_count > 0


# ==============================================================================
# Phase 2.9: Rate Limiting Logic (6 tests)
# ==============================================================================


class TestAuthServiceRateLimiting:
    """Tests for AuthService rate limiting logic."""

    @pytest.mark.asyncio
    async def test_get_lockout_duration_below_threshold(self, user_auth_app_manager):
        """Test lockout duration with attempt count below threshold."""
        auth_service = user_auth_app_manager.get_service("auth")

        # Default config: {3: 60, 5: 900}
        # Attempts below 3 should have no lockout
        assert auth_service._get_lockout_duration(1) == 0
        assert auth_service._get_lockout_duration(2) == 0

    @pytest.mark.asyncio
    async def test_get_lockout_duration_first_threshold(self, user_auth_app_manager):
        """Test lockout duration at first threshold (3 attempts = 60 seconds)."""
        auth_service = user_auth_app_manager.get_service("auth")

        # 3-4 attempts should trigger 60 second lockout
        assert auth_service._get_lockout_duration(3) == 60
        assert auth_service._get_lockout_duration(4) == 60

    @pytest.mark.asyncio
    async def test_get_lockout_duration_second_threshold(self, user_auth_app_manager):
        """Test lockout duration at second threshold (5+ attempts = 900 seconds)."""
        auth_service = user_auth_app_manager.get_service("auth")

        # 5+ attempts should trigger 900 second lockout
        assert auth_service._get_lockout_duration(5) == 900
        assert auth_service._get_lockout_duration(10) == 900
        assert auth_service._get_lockout_duration(100) == 900

    @pytest.mark.asyncio
    async def test_authenticate_user_rate_limit_blocks_login(self, user_auth_app_manager):
        """Test that rate limiting blocks login when user is locked out."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        user_login_attempt_entity = user_auth_app_manager.get_entity("user_login_attempt")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Create failed attempt with active lockout
            blocked_until = now_utc() + timedelta(seconds=300)
            attempt = user_login_attempt_entity(
                status_id=FAILED_LOGIN_ATTEMPT_STATUS,
                user_id=user.id,
                attempt_count=5,
                blocked_until=blocked_until
            )
            session.add(attempt)
            await session.commit()

            # Try to authenticate - should raise rate limit error
            with pytest.raises(LysError) as exc_info:
                await auth_service.authenticate_user(email, "Password123!", session)

            assert exc_info.value.status_code == RATE_LIMIT_ERROR[0]
            assert exc_info.value.detail == "RATE_LIMIT_ERROR"
            assert "remaining_seconds" in exc_info.value.extensions
            assert "attempt_count" in exc_info.value.extensions
            assert exc_info.value.extensions["attempt_count"] == 5

    @pytest.mark.asyncio
    async def test_authenticate_user_rate_limit_expires(self, user_auth_app_manager):
        """Test that expired rate limit allows authentication."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        user_login_attempt_entity = user_auth_app_manager.get_entity("user_login_attempt")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Create failed attempt with expired lockout
            blocked_until = now_utc() - timedelta(seconds=10)  # Already expired
            attempt = user_login_attempt_entity(
                status_id=FAILED_LOGIN_ATTEMPT_STATUS,
                user_id=user.id,
                attempt_count=5,
                blocked_until=blocked_until
            )
            session.add(attempt)
            await session.commit()

            # Try to authenticate with correct password - should succeed
            result = await auth_service.authenticate_user(email, "Password123!", session)

            assert result is not None
            assert result.id == user.id

    @pytest.mark.asyncio
    async def test_authenticate_user_rate_limit_disabled(self, user_auth_app_manager):
        """Test authentication with rate limiting disabled."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        user_login_attempt_entity = user_auth_app_manager.get_entity("user_login_attempt")
        email = unique_email()

        # Mock auth_utils.config to disable rate limiting
        with patch.object(auth_service.auth_utils, 'config', {"login_rate_limit_enabled": False}):
            async with user_auth_app_manager.database.get_session() as session:
                # Create test user
                user = await user_service._create_user_internal(
                    session=session,
                    email=email,
                    password="Password123!",
                    language_id="en",
                    is_super_user=False,
                    send_verification_email=False
                )
                await session.commit()

                # Create failed attempt with active lockout
                blocked_until = now_utc() + timedelta(seconds=300)
                attempt = user_login_attempt_entity(
                    status_id=FAILED_LOGIN_ATTEMPT_STATUS,
                    user_id=user.id,
                    attempt_count=5,
                    blocked_until=blocked_until
                )
                session.add(attempt)
                await session.commit()

                # Try to authenticate with correct password - should succeed despite lockout
                result = await auth_service.authenticate_user(email, "Password123!", session)

                assert result is not None
                assert result.id == user.id


# ==============================================================================
# Phase 2.10: Authentication Flow (10 tests)
# ==============================================================================


class TestAuthServiceAuthenticationFlow:
    """Tests for AuthService authentication flow."""

    @pytest.mark.asyncio
    async def test_authenticate_user_with_valid_credentials(self, user_auth_app_manager):
        """Test successful authentication with valid credentials."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Authenticate with correct password
            result = await auth_service.authenticate_user(email, "Password123!", session)

            assert result is not None
            assert result.id == user.id
            assert result.email_address.address == email

    @pytest.mark.asyncio
    async def test_authenticate_user_with_wrong_password(self, user_auth_app_manager):
        """Test authentication failure with wrong password returns None."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Authenticate with wrong password
            result = await auth_service.authenticate_user(email, "WrongPassword!", session)

            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_with_nonexistent_user(self, user_auth_app_manager):
        """Test authentication with nonexistent user raises INVALID_CREDENTIALS_ERROR."""
        auth_service = user_auth_app_manager.get_service("auth")

        async with user_auth_app_manager.database.get_session() as session:
            # Try to authenticate nonexistent user - should raise (prevents user enumeration)
            with pytest.raises(LysError) as exc_info:
                await auth_service.authenticate_user("nonexistent@example.com", "Password123!", session)

            assert exc_info.value.status_code == INVALID_CREDENTIALS_ERROR[0]

    @pytest.mark.asyncio
    async def test_authenticate_user_with_disabled_user(self, user_auth_app_manager):
        """Test authentication with disabled user raises blocked error."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            # Disable user
            user.status_id = DISABLED_USER_STATUS
            await session.commit()

            # Try to authenticate disabled user
            with pytest.raises(LysError) as exc_info:
                await auth_service.authenticate_user(email, "Password123!", session)

            assert exc_info.value.status_code == INVALID_CREDENTIALS_ERROR[0]

    @pytest.mark.asyncio
    async def test_failed_login_after_failed_increments_count(self, user_auth_app_manager):
        """Test that failed login after failed increments attempt count on same line."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        user_login_attempt_entity = user_auth_app_manager.get_entity("user_login_attempt")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Create previous failed login attempt
            failed_attempt = user_login_attempt_entity(
                status_id=FAILED_LOGIN_ATTEMPT_STATUS,
                user_id=user.id,
                attempt_count=1,
                blocked_until=None
            )
            session.add(failed_attempt)
            await session.commit()
            failed_attempt_id = failed_attempt.id

            # Authenticate with wrong password again (should increment same line)
            result = await auth_service.authenticate_user(email, "WrongPassword!", session)
            await session.commit()

            assert result is None

            # Verify same line was updated
            last_attempt = await auth_service.get_user_last_login_attempt(user, session)
            assert last_attempt is not None
            assert last_attempt.id == failed_attempt_id  # Same line
            assert last_attempt.attempt_count == 2  # Incremented

    @pytest.mark.asyncio
    async def test_multiple_failed_attempts_increment_correctly(self, user_auth_app_manager):
        """Test that multiple consecutive failed attempts increment correctly."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        # Disable rate limiting to test pure logic
        with patch.object(auth_service.auth_utils, 'config', {"login_rate_limit_enabled": False}):
            async with user_auth_app_manager.database.get_session() as session:
                # Create test user
                user = await user_service._create_user_internal(
                    session=session,
                    email=email,
                    password="Password123!",
                    language_id="en",
                    is_super_user=False,
                    send_verification_email=False
                )
                await session.commit()

                # Make 5 consecutive failed attempts
                for i in range(5):
                    result = await auth_service.authenticate_user(email, "WrongPassword!", session)
                    await session.commit()
                    assert result is None

                    # Check attempt count after each failure
                    last_attempt = await auth_service.get_user_last_login_attempt(user, session)
                    assert last_attempt is not None
                    assert last_attempt.status_id == FAILED_LOGIN_ATTEMPT_STATUS
                    assert last_attempt.attempt_count == i + 1

    @pytest.mark.asyncio
    async def test_authenticate_user_with_no_previous_attempts(self, user_auth_app_manager):
        """Test authentication creates login attempt even with no previous attempts."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        email = unique_email()

        async with user_auth_app_manager.database.get_session() as session:
            # Create test user
            user = await user_service._create_user_internal(
                session=session,
                email=email,
                password="Password123!",
                language_id="en",
                is_super_user=False,
                send_verification_email=False
            )
            await session.commit()

            # Verify no previous attempts
            last_attempt = await auth_service.get_user_last_login_attempt(user, session)
            assert last_attempt is None

            # Authenticate with correct password
            result = await auth_service.authenticate_user(email, "Password123!", session)
            await session.commit()

            assert result is not None
            assert result.id == user.id

            # Verify success attempt was created
            last_attempt = await auth_service.get_user_last_login_attempt(user, session)
            assert last_attempt is not None
            assert last_attempt.status_id == SUCCEED_LOGIN_ATTEMPT_STATUS
            assert last_attempt.attempt_count == 1


# ==============================================================================
# Phase 1A: generate_access_claims and generate_access_token tests
# ==============================================================================


class TestGenerateAccessClaims:
    """Test AuthService.generate_access_claims operations."""

    @pytest.mark.asyncio
    async def test_generate_access_claims_normal_user(self, user_auth_app_manager):
        """Test generating claims for a normal user includes expected fields."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")

        email = unique_email()
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            claims = await auth_service.generate_access_claims(user, session)

            assert "sub" in claims
            assert claims["sub"] == str(user.id)
            assert claims["is_super_user"] is False
            assert "webservices" in claims
            assert isinstance(claims["webservices"], dict)

    @pytest.mark.asyncio
    async def test_generate_access_claims_super_user(self, user_auth_app_manager):
        """Test generating claims for a super user."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")

        email = unique_email()
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=True, send_verification_email=False
            )
            await session.commit()

            claims = await auth_service.generate_access_claims(user, session)

            assert claims["sub"] == str(user.id)
            assert claims["is_super_user"] is True


class TestGenerateAccessToken:
    """Test AuthService.generate_access_token operations."""

    @pytest.mark.asyncio
    async def test_generate_access_token_returns_valid_jwt(self, user_auth_app_manager):
        """Test that generate_access_token returns a valid JWT string and claims."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")

        email = unique_email()
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            # Patch auth_utils config for token generation
            original_config = auth_service.auth_utils.config
            original_secret = auth_service.auth_utils.secret_key
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            auth_service.auth_utils.secret_key = _TEST_SECRET_KEY
            try:
                token_str, claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config
                auth_service.auth_utils.secret_key = original_secret

            # Token should be a non-empty string
            assert isinstance(token_str, str)
            assert len(token_str) > 0

            # Claims should include standard JWT fields
            assert "exp" in claims
            assert "xsrf_token" in claims
            assert "sub" in claims
            assert claims["sub"] == str(user.id)

            # Token should be decodable and contain iss/aud
            decoded = jwt.decode(
                token_str, _TEST_SECRET_KEY, algorithms=["HS256"],
                audience="lys-api",
            )
            assert decoded["sub"] == str(user.id)
            assert decoded["iss"] == "lys-auth"
            assert decoded["aud"] == "lys-api"

    @pytest.mark.asyncio
    async def test_generate_access_token_has_expiry(self, user_auth_app_manager):
        """Test that generated token has a future expiry timestamp."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")

        email = unique_email()
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            original_config = auth_service.auth_utils.config
            original_secret = auth_service.auth_utils.secret_key
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            auth_service.auth_utils.secret_key = _TEST_SECRET_KEY
            try:
                _, claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config
                auth_service.auth_utils.secret_key = original_secret

            # Expiry should be in the future
            assert claims["exp"] > int(now_utc().timestamp())


class TestLogout:
    """Test AuthService.logout operations."""

    @pytest.mark.asyncio
    async def test_logout_with_refresh_token(self, user_auth_app_manager):
        """Test logout revokes refresh token and clears cookies."""
        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")
        refresh_token_service = user_auth_app_manager.get_service("user_refresh_token")

        email = unique_email()
        async with user_auth_app_manager.database.get_session() as session:
            user = await user_service._create_user_internal(
                session=session, email=email, password="Password123!",
                language_id="en", is_super_user=False, send_verification_email=False
            )
            await session.commit()

            # Generate a refresh token (needs auth config)
            with patch("lys.apps.user_auth.modules.user.services.AuthUtils") as mock_auth:
                mock_auth.return_value.config = _TEST_AUTH_CONFIG
                token = await refresh_token_service.generate(user, session=session)
                await session.commit()

            # Create mock request/response
            request = MagicMock()
            request.cookies = {REFRESH_COOKIE_KEY: token.id}
            response = Response()

            original_config = auth_service.auth_utils.config
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                await auth_service.logout(request, response, session)
            finally:
                auth_service.auth_utils.config = original_config
            await session.commit()

        # Verify token was revoked
        async with user_auth_app_manager.database.get_session() as session:
            revoked = await refresh_token_service.get_by_id(token.id, session)
            assert revoked.revoked_at is not None

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(self, user_auth_app_manager):
        """Test logout without refresh token cookie does not crash."""
        auth_service = user_auth_app_manager.get_service("auth")

        async with user_auth_app_manager.database.get_session() as session:
            request = MagicMock()
            request.cookies = {}
            response = Response()

            original_config = auth_service.auth_utils.config
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                await auth_service.logout(request, response, session)
            finally:
                auth_service.auth_utils.config = original_config
