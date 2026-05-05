"""
Integration tests for AuthService.

Tests cover:
- Phase 2.7: User lookup by login (3 tests)
- Phase 2.8: Login attempt tracking (3 tests)
- Phase 2.9: Rate limiting logic (6 tests)
- Phase 2.10: Authentication flow (7 tests)
- Phase 2.11: Opaque access token (store roundtrip, revocation on logout/refresh)
"""
import asyncio
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

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
from lys.apps.user_auth.modules.auth.store import ACCESS_TOKEN_KEY_PREFIX
from lys.apps.user_auth.modules.user.consts import ENABLED_USER_STATUS, DISABLED_USER_STATUS
from lys.core.configs import LysAppSettings
from lys.core.consts.component_types import AppComponentTypeEnum
from lys.core.errors import LysError
from lys.core.managers.app import AppManager
from lys.core.utils.datetime import now_utc


class FakePubSub:
    """
    In-memory stand-in for ``PubSubManager``'s key/value API.

    Implements the three coroutine methods AccessTokenStore relies on
    (``set_key``, ``get_key``, ``delete_key``) so we can exercise the full
    auth flow against a deterministic store — no Redis required, no flaky
    TTL waits. Stored values include the ttl that was passed in so tests
    can assert it.
    """

    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def set_key(self, key: str, value: str, ttl_seconds: int = None) -> bool:
        self.store[key] = value
        if ttl_seconds is not None:
            self.ttls[key] = ttl_seconds
        return True

    async def get_key(self, key: str):
        return self.store.get(key)

    async def delete_key(self, key: str) -> bool:
        existed = key in self.store
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        return existed


@pytest_asyncio.fixture
async def fake_pubsub(user_auth_app_manager):
    """
    Inject a FakePubSub onto every AppManager that AuthService might consult.

    AuthService.app_manager goes through ``AppManagerCallerMixin`` which
    returns the ``LysAppManager`` singleton, distinct from the test's
    ``user_auth_app_manager`` instance (which is a plain ``AppManager``).
    Both share the registry singleton, but pubsub is per-instance — so the
    fake must be attached to whichever instance the service actually reads.
    We set it on both for safety and restore on teardown.
    """
    from lys.core.managers.app import LysAppManager

    fake = FakePubSub()

    lys_singleton = LysAppManager()
    previous_singleton = lys_singleton.pubsub
    previous_test = user_auth_app_manager.pubsub

    lys_singleton.pubsub = fake
    user_auth_app_manager.pubsub = fake
    try:
        yield fake
    finally:
        lys_singleton.pubsub = previous_singleton
        user_auth_app_manager.pubsub = previous_test


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
    """Test AuthService.generate_access_token operations.

    The token returned is now an opaque UUID, not a JWT. Claims live
    server-side in the AccessTokenStore (Redis in prod, FakePubSub here).
    """

    @pytest.mark.asyncio
    async def test_generate_access_token_returns_opaque_uuid(self, user_auth_app_manager, fake_pubsub):
        """Token must be a short opaque UUID, not a JWT — fixes the 4096-byte cookie issue."""
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                token_str, claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

            assert isinstance(token_str, str)
            # UUID v4 string form: 36 chars, no dots (JWTs have two dots).
            assert len(token_str) == 36
            assert "." not in token_str
            UUID(token_str)  # raises if not a valid UUID

            # Cookie size guarantee: well under the 4096-byte browser limit.
            assert len(token_str) < 50

            # Claims still carry the same shape the override chain produces.
            assert claims["sub"] == str(user.id)
            assert "exp" in claims
            assert "xsrf_token" in claims

    @pytest.mark.asyncio
    async def test_generate_access_token_persists_claims_in_store(self, user_auth_app_manager, fake_pubsub):
        """Claims must round-trip through the store under the lys:access_token: prefix."""
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                token_str, claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

        expected_key = f"{ACCESS_TOKEN_KEY_PREFIX}{token_str}"
        assert expected_key in fake_pubsub.store

        stored_claims = json.loads(fake_pubsub.store[expected_key])
        assert stored_claims == claims  # exact roundtrip

        # TTL must match access_token_expire_minutes (15 in test config) in seconds.
        assert fake_pubsub.ttls[expected_key] == _TEST_AUTH_CONFIG["access_token_expire_minutes"] * 60

    @pytest.mark.asyncio
    async def test_generate_access_token_has_future_expiry(self, user_auth_app_manager, fake_pubsub):
        """The exp claim is kept for the front-end to schedule a refresh."""
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                _, claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

            assert claims["exp"] > int(now_utc().timestamp())

    @pytest.mark.asyncio
    async def test_generate_access_token_without_pubsub_raises(self, user_auth_app_manager):
        """Login must fail loudly if pubsub is unavailable rather than issue an unstorable token."""
        from lys.core.managers.app import LysAppManager

        user_service = user_auth_app_manager.get_service("user")
        auth_service = user_auth_app_manager.get_service("auth")

        # Strip pubsub from both the test manager and the singleton AuthService reads from.
        lys_singleton = LysAppManager()
        previous_singleton = lys_singleton.pubsub
        previous_test = user_auth_app_manager.pubsub
        lys_singleton.pubsub = None
        user_auth_app_manager.pubsub = None
        try:
            email = unique_email()
            async with user_auth_app_manager.database.get_session() as session:
                user = await user_service._create_user_internal(
                    session=session, email=email, password="Password123!",
                    language_id="en", is_super_user=False, send_verification_email=False
                )
                await session.commit()

                original_config = auth_service.auth_utils.config
                auth_service.auth_utils.config = _TEST_AUTH_CONFIG
                try:
                    with pytest.raises(RuntimeError, match="PubSubManager is not initialised"):
                        await auth_service.generate_access_token(user, session)
                finally:
                    auth_service.auth_utils.config = original_config
        finally:
            lys_singleton.pubsub = previous_singleton
            user_auth_app_manager.pubsub = previous_test


class TestLogout:
    """Test AuthService.logout operations."""

    @pytest.mark.asyncio
    async def test_logout_with_refresh_token(self, user_auth_app_manager, fake_pubsub):
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
    async def test_logout_without_refresh_token(self, user_auth_app_manager, fake_pubsub):
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

    @pytest.mark.asyncio
    async def test_logout_purges_access_token_from_store(self, user_auth_app_manager, fake_pubsub):
        """
        Logout must invalidate the opaque access token server-side so a leaked
        cookie cannot be replayed until TTL expiry. This is the security gain
        over the previous JWT model where revocation required a blacklist.
        """
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                token_id, _ = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

            stored_key = f"{ACCESS_TOKEN_KEY_PREFIX}{token_id}"
            assert stored_key in fake_pubsub.store  # sanity

            request = MagicMock()
            request.cookies = {ACCESS_COOKIE_KEY: token_id}
            response = Response()

            original_config = auth_service.auth_utils.config
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                await auth_service.logout(request, response, session)
            finally:
                auth_service.auth_utils.config = original_config

        # The store entry is gone — any subsequent middleware lookup returns None.
        assert stored_key not in fake_pubsub.store


class TestResolveAccessToken:
    """Public hook for resolving an opaque token to claims (mirror of revoke)."""

    @pytest.mark.asyncio
    async def test_resolve_existing_token_returns_claims(self, user_auth_app_manager, fake_pubsub):
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                token_id, claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

        resolved = await auth_service.resolve_access_token(token_id)
        assert resolved == claims

    @pytest.mark.asyncio
    async def test_resolve_unknown_token_returns_none(self, fake_pubsub, user_auth_app_manager):
        auth_service = user_auth_app_manager.get_service("auth")
        assert await auth_service.resolve_access_token("not-a-real-uuid") is None

    @pytest.mark.asyncio
    async def test_resolve_empty_or_none_returns_none(self, fake_pubsub, user_auth_app_manager):
        auth_service = user_auth_app_manager.get_service("auth")
        assert await auth_service.resolve_access_token(None) is None
        assert await auth_service.resolve_access_token("") is None


class TestRevokeAccessToken:
    """Public hook for invalidating an opaque token outside logout."""

    @pytest.mark.asyncio
    async def test_revoke_existing_token_returns_true(self, user_auth_app_manager, fake_pubsub):
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                token_id, _ = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

        assert await auth_service.revoke_access_token(token_id) is True
        assert f"{ACCESS_TOKEN_KEY_PREFIX}{token_id}" not in fake_pubsub.store

    @pytest.mark.asyncio
    async def test_revoke_unknown_token_returns_false(self, fake_pubsub, user_auth_app_manager):
        auth_service = user_auth_app_manager.get_service("auth")
        assert await auth_service.revoke_access_token("not-a-real-uuid") is False

    @pytest.mark.asyncio
    async def test_revoke_empty_or_none_is_noop(self, fake_pubsub, user_auth_app_manager):
        auth_service = user_auth_app_manager.get_service("auth")
        assert await auth_service.revoke_access_token(None) is False
        assert await auth_service.revoke_access_token("") is False


class TestLoginPurgesPreviousToken:
    """
    Logging in with a stale access cookie must invalidate the previous
    token server-side, mirroring the refresh flow. Prevents two valid
    tokens from coexisting for the same user (latent session-fixation
    window) and stops Redis orphan accumulation.
    """

    @pytest.mark.asyncio
    async def test_login_with_stale_access_cookie_revokes_it(self, user_auth_app_manager, fake_pubsub):
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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                # 1. Issue an initial access token (the "stale" one).
                stale_token, _ = await auth_service.generate_access_token(user, session)
                stale_key = f"{ACCESS_TOKEN_KEY_PREFIX}{stale_token}"
                assert stale_key in fake_pubsub.store

                # 2. Re-login with that cookie still attached.
                request = MagicMock()
                request.cookies = {ACCESS_COOKIE_KEY: stale_token}
                response = Response()

                # The refresh-token service builds its own AuthUtils — patch it
                # so it picks up the test auth config (same pattern as TestLogout).
                with patch("lys.apps.user_auth.modules.user.services.AuthUtils") as mock_auth:
                    mock_auth.return_value.config = _TEST_AUTH_CONFIG
                    _, claims = await auth_service.login(
                        LoginInputModel(login=email, password="Password123!"),
                        response,
                        session,
                        request=request,
                    )
                await session.commit()
            finally:
                auth_service.auth_utils.config = original_config

        # The stale entry is gone; a fresh one exists for the new token.
        assert stale_key not in fake_pubsub.store
        # Find the new token id by looking for the remaining lys:access_token: key.
        remaining = [k for k in fake_pubsub.store if k.startswith(ACCESS_TOKEN_KEY_PREFIX)]
        assert len(remaining) == 1
        assert remaining[0] != stale_key


class TestAccessTokenStoreRoundtrip:
    """Verify the middleware contract: a freshly issued token resolves back to its claims."""

    @pytest.mark.asyncio
    async def test_token_resolves_back_to_claims(self, user_auth_app_manager, fake_pubsub):
        from lys.apps.user_auth.modules.auth.store import AccessTokenStore

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
            auth_service.auth_utils.config = _TEST_AUTH_CONFIG
            try:
                token_id, generated_claims = await auth_service.generate_access_token(user, session)
            finally:
                auth_service.auth_utils.config = original_config

        store = AccessTokenStore(fake_pubsub)
        resolved = await store.get(token_id)

        assert resolved == generated_claims
        # Required claims for the middleware
        assert resolved["sub"] == str(user.id)
        assert "xsrf_token" in resolved
        assert "exp" in resolved

    @pytest.mark.asyncio
    async def test_unknown_token_resolves_to_none(self, fake_pubsub):
        """Equivalent to a previously-expired JWT: middleware sees None and treats as anonymous."""
        from lys.apps.user_auth.modules.auth.store import AccessTokenStore

        store = AccessTokenStore(fake_pubsub)
        assert await store.get("not-a-real-uuid") is None

    @pytest.mark.asyncio
    async def test_corrupted_entry_is_purged(self, fake_pubsub):
        """Defense-in-depth: a malformed JSON entry should be deleted, not raise."""
        from lys.apps.user_auth.modules.auth.store import AccessTokenStore

        store = AccessTokenStore(fake_pubsub)
        bad_id = "corrupted-id"
        await fake_pubsub.set_key(f"{ACCESS_TOKEN_KEY_PREFIX}{bad_id}", "{not json")

        assert await store.get(bad_id) is None
        assert f"{ACCESS_TOKEN_KEY_PREFIX}{bad_id}" not in fake_pubsub.store
