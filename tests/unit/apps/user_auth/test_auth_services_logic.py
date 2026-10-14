"""
Unit tests for AuthService logic (_get_lockout_duration, generate_xsrf_token,
set_auth_cookies, clear_auth_cookies, authenticate_user anti-enumeration).

Isolation: Uses patch.object to avoid touching the AuthUtils singleton.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestGetLockoutDuration:
    """Tests for AuthService._get_lockout_duration() — pure logic."""

    def _call(self, attempt_count, durations=None):
        """Call _get_lockout_duration with mocked auth_utils config."""
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_config = {}
        if durations is not None:
            mock_config["login_lockout_durations"] = durations
        with patch.object(AuthService, "auth_utils", create=True) as mock_utils:
            mock_utils.config = mock_config
            return AuthService._get_lockout_duration(attempt_count)

    def test_below_threshold_returns_zero(self):
        assert self._call(1, {3: 60, 5: 900}) == 0

    def test_at_first_threshold(self):
        assert self._call(3, {3: 60, 5: 900}) == 60

    def test_between_thresholds(self):
        assert self._call(4, {3: 60, 5: 900}) == 60

    def test_at_second_threshold(self):
        assert self._call(5, {3: 60, 5: 900}) == 900

    def test_above_all_thresholds(self):
        assert self._call(10, {3: 60, 5: 900}) == 900

    def test_default_durations_used(self):
        # When no durations in config, defaults are {3: 60, 5: 900}
        assert self._call(3) == 60
        assert self._call(5) == 900

    def test_single_threshold(self):
        assert self._call(2, {2: 120}) == 120


class TestGenerateXsrfToken:
    """Tests for AuthService.generate_xsrf_token()."""

    @pytest.mark.asyncio
    async def test_returns_bytes(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        token = await AuthService.generate_xsrf_token()
        assert isinstance(token, bytes)

    @pytest.mark.asyncio
    async def test_is_hex_encoded(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        token = await AuthService.generate_xsrf_token()
        # Should be valid hex (128 hex chars = 64 bytes)
        decoded = token.decode("ascii")
        int(decoded, 16)  # Should not raise
        assert len(decoded) == 128

    @pytest.mark.asyncio
    async def test_tokens_are_unique(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        t1 = await AuthService.generate_xsrf_token()
        t2 = await AuthService.generate_xsrf_token()
        assert t1 != t2


class TestSetAuthCookies:
    """Tests for AuthService.set_auth_cookies() and clear_auth_cookies()."""

    @pytest.mark.asyncio
    async def test_set_auth_cookies_calls_set_cookie(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_response = Mock()

        with patch.object(AuthService, "set_cookie", new_callable=AsyncMock) as mock_set:
            await AuthService.set_auth_cookies(mock_response, "refresh-id", "access-jwt")
            assert mock_set.call_count == 2
            # First call: refresh token
            assert mock_set.call_args_list[0][0][1] == "refresh_token"
            assert mock_set.call_args_list[0][0][2] == "refresh-id"
            # Second call: access token
            assert mock_set.call_args_list[1][0][1] == "access_token"
            assert mock_set.call_args_list[1][0][2] == "access-jwt"

    @pytest.mark.asyncio
    async def test_clear_auth_cookies(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_response = Mock()
        await AuthService.clear_auth_cookies(mock_response)
        assert mock_response.delete_cookie.call_count == 3
        deleted_keys = [c[1].get("key", c[0][0]) for c in mock_response.delete_cookie.call_args_list]
        assert "refresh_token" in deleted_keys
        assert "access_token" in deleted_keys
        assert "XSRF-TOKEN" in deleted_keys


class TestSetCookieDefaults:
    """Tests for AuthService.set_cookie() secure defaults."""

    @pytest.mark.asyncio
    async def test_defaults_secure_true(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_response = Mock()
        with patch.object(AuthService, "auth_utils", create=True) as mock_utils:
            mock_utils.config = {}
            await AuthService.set_cookie(mock_response, "key", "value", "/")
        call_kwargs = mock_response.set_cookie.call_args[1]
        assert call_kwargs["secure"] is True

    @pytest.mark.asyncio
    async def test_defaults_httponly_true(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_response = Mock()
        with patch.object(AuthService, "auth_utils", create=True) as mock_utils:
            mock_utils.config = {}
            await AuthService.set_cookie(mock_response, "key", "value", "/")
        call_kwargs = mock_response.set_cookie.call_args[1]
        assert call_kwargs["httponly"] is True

    @pytest.mark.asyncio
    async def test_defaults_samesite_lax(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_response = Mock()
        with patch.object(AuthService, "auth_utils", create=True) as mock_utils:
            mock_utils.config = {}
            await AuthService.set_cookie(mock_response, "key", "value", "/")
        call_kwargs = mock_response.set_cookie.call_args[1]
        assert call_kwargs["samesite"] == "Lax"

    @pytest.mark.asyncio
    async def test_config_overrides_defaults(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        mock_response = Mock()
        with patch.object(AuthService, "auth_utils", create=True) as mock_utils:
            mock_utils.config = {
                "cookie_secure": False,
                "cookie_http_only": False,
                "cookie_same_site": "Strict",
            }
            await AuthService.set_cookie(mock_response, "key", "value", "/")
        call_kwargs = mock_response.set_cookie.call_args[1]
        assert call_kwargs["secure"] is False
        assert call_kwargs["httponly"] is False
        assert call_kwargs["samesite"] == "Strict"


class TestDummyHash:
    """Tests for _DUMMY_HASH constant used for timing equalization."""

    def test_dummy_hash_is_valid_bcrypt(self):
        import bcrypt
        from lys.apps.user_auth.modules.auth.services import _DUMMY_HASH
        # Must be a valid bcrypt hash (starts with $2b$)
        assert _DUMMY_HASH.startswith("$2b$")

    def test_dummy_hash_is_string(self):
        from lys.apps.user_auth.modules.auth.services import _DUMMY_HASH
        assert isinstance(_DUMMY_HASH, str)


class TestAuthenticateUserAntiEnumeration:
    """Tests for user enumeration prevention in authenticate_user."""

    @pytest.mark.asyncio
    async def test_user_not_found_raises_invalid_credentials(self):
        """User not found must raise INVALID_CREDENTIALS_ERROR (not a distinct error)."""
        from lys.apps.user_auth.modules.auth.services import AuthService
        from lys.apps.user_auth.errors import INVALID_CREDENTIALS_ERROR
        from lys.core.errors import LysError

        mock_session = AsyncMock()

        with patch.object(AuthService, "get_user_from_login", new_callable=AsyncMock, return_value=None), \
             patch.object(AuthService, "app_manager", create=True):
            with pytest.raises(LysError) as exc_info:
                await AuthService.authenticate_user("unknown@test.com", "password", mock_session)
            assert exc_info.value.status_code == INVALID_CREDENTIALS_ERROR[0]
            assert exc_info.value.detail == INVALID_CREDENTIALS_ERROR[1]

    @pytest.mark.asyncio
    async def test_user_not_found_runs_bcrypt(self):
        """Dummy bcrypt must run when user not found to equalize timing."""
        import bcrypt
        from lys.apps.user_auth.modules.auth.services import AuthService
        from lys.core.errors import LysError

        mock_session = AsyncMock()

        with patch.object(AuthService, "get_user_from_login", new_callable=AsyncMock, return_value=None), \
             patch.object(AuthService, "app_manager", create=True), \
             patch.object(bcrypt, "checkpw", return_value=False) as mock_checkpw:
            with pytest.raises(LysError):
                await AuthService.authenticate_user("unknown@test.com", "password", mock_session)
            mock_checkpw.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocked_user_raises_invalid_credentials(self):
        """Blocked user with correct password must raise INVALID_CREDENTIALS_ERROR."""
        from lys.apps.user_auth.modules.auth.services import AuthService
        from lys.apps.user_auth.errors import INVALID_CREDENTIALS_ERROR
        from lys.core.errors import LysError

        mock_session = AsyncMock()
        mock_user = Mock()
        mock_user.status_id = "DISABLED"

        with patch.object(AuthService, "get_user_from_login", new_callable=AsyncMock, return_value=mock_user), \
             patch.object(AuthService, "get_user_last_login_attempt", new_callable=AsyncMock, return_value=None), \
             patch.object(AuthService, "auth_utils", create=True) as mock_utils, \
             patch.object(AuthService, "app_manager", create=True) as mock_am:
            mock_utils.config = {"login_rate_limit_enabled": True}
            mock_user_service = Mock()
            mock_user_service.check_password.return_value = True
            mock_am.get_service.return_value = mock_user_service
            mock_am.get_entity.return_value = Mock

            with pytest.raises(LysError) as exc_info:
                await AuthService.authenticate_user("user@test.com", "correct-pw", mock_session)
            assert exc_info.value.status_code == INVALID_CREDENTIALS_ERROR[0]
            assert exc_info.value.detail == INVALID_CREDENTIALS_ERROR[1]

    @pytest.mark.asyncio
    async def test_wrong_password_returns_none(self):
        """Wrong password must return None (same as user-not-found from caller's perspective)."""
        from lys.apps.user_auth.modules.auth.services import AuthService
        from lys.apps.user_auth.modules.auth.consts import FAILED_LOGIN_ATTEMPT_STATUS

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # add() is synchronous on AsyncSession
        mock_user = Mock()
        mock_user.id = "user-1"
        mock_user.status_id = "ENABLED"

        mock_attempt_entity = Mock()

        with patch.object(AuthService, "get_user_from_login", new_callable=AsyncMock, return_value=mock_user), \
             patch.object(AuthService, "get_user_last_login_attempt", new_callable=AsyncMock, return_value=None), \
             patch.object(AuthService, "auth_utils", create=True) as mock_utils, \
             patch.object(AuthService, "app_manager", create=True) as mock_am:
            mock_utils.config = {"login_rate_limit_enabled": False}
            mock_user_service = Mock()
            mock_user_service.check_password.return_value = False
            mock_am.get_service.return_value = mock_user_service
            mock_am.get_entity.return_value = mock_attempt_entity

            result = await AuthService.authenticate_user("user@test.com", "wrong-pw", mock_session)
            assert result is None


class TestRecordSuccessfulLogin:
    """Tests for AuthService.record_successful_login() — the success row of the login history."""

    @pytest.mark.asyncio
    async def test_adds_a_success_row_for_the_user(self):
        from lys.apps.user_auth.modules.auth.services import AuthService
        from lys.apps.user_auth.modules.auth.consts import SUCCEED_LOGIN_ATTEMPT_STATUS

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_user = Mock()
        mock_user.id = "user-1"
        mock_attempt_entity = Mock()

        with patch.object(AuthService, "app_manager", create=True) as mock_am:
            mock_am.get_entity.return_value = mock_attempt_entity
            row = await AuthService.record_successful_login(mock_user, mock_session)

        mock_attempt_entity.assert_called_once_with(
            status_id=SUCCEED_LOGIN_ATTEMPT_STATUS, user_id="user-1", attempt_count=1, blocked_until=None
        )
        mock_session.add.assert_called_once_with(row)


class TestGetPreviousSuccessfulLoginAt:
    """Tests for AuthService.get_previous_successful_login_at()."""

    @pytest.mark.asyncio
    async def test_flushes_the_pending_login_before_reading(self):
        """The login just recorded may be pending: without a flush, offset(1) would skip the wrong row."""
        from datetime import datetime, timezone
        from lys.apps.user_auth.modules.auth.entities import UserLoginAttempt
        from lys.apps.user_auth.modules.auth.services import AuthService

        previous = datetime(2026, 10, 1, tzinfo=timezone.utc)
        calls = []
        mock_session = AsyncMock()
        mock_session.flush.side_effect = lambda: calls.append("flush")
        result = MagicMock()
        result.scalar_one_or_none.return_value = previous

        async def execute(stmt):
            calls.append("execute")
            return result

        mock_session.execute.side_effect = execute

        with patch.object(AuthService, "app_manager", create=True) as mock_am:
            mock_am.get_entity.return_value = UserLoginAttempt
            value = await AuthService.get_previous_successful_login_at("user-1", mock_session)

        assert value == previous
        assert calls == ["flush", "execute"]
        stmt = mock_session.execute.call_args.args[0]
        assert stmt._offset_clause.value == 1


class TestOpenSession:
    """Tests for AuthService.open_session() — tokens of a new session, shared by every credential path."""

    @pytest.mark.asyncio
    async def test_previous_login_is_carried_by_both_tokens(self):
        from datetime import datetime, timezone
        from lys.apps.user_auth.modules.auth.services import AuthService

        previous = datetime(2026, 10, 1, tzinfo=timezone.utc)
        mock_session = AsyncMock()
        response = Mock()
        mock_user = Mock()
        mock_user.id = "user-1"
        refresh_token = Mock()
        refresh_token.id = "refresh-1"
        refresh_service = Mock()
        refresh_service.generate = AsyncMock(return_value=refresh_token)
        claims = {"sub": "user-1", "xsrf_token": "xsrf-1"}

        with patch.object(AuthService, "app_manager", create=True) as mock_am, \
             patch.object(AuthService, "get_previous_successful_login_at",
                          new_callable=AsyncMock, return_value=previous), \
             patch.object(AuthService, "generate_access_token",
                          new_callable=AsyncMock, return_value=("access-1", claims)) as mock_access, \
             patch.object(AuthService, "set_auth_cookies", new_callable=AsyncMock) as mock_cookies:
            mock_am.get_service.return_value = refresh_service
            result = await AuthService.open_session(mock_user, response, mock_session)

        assert result is claims
        refresh_service.generate.assert_awaited_once_with(
            mock_user, session=mock_session, previous_login_at=previous
        )
        mock_access.assert_awaited_once_with(mock_user, mock_session, previous_login_at=previous)
        mock_cookies.assert_awaited_once_with(response, "refresh-1", "access-1", "xsrf-1")


class TestGenerateAccessTokenPreviousLoginClaim:
    """Tests for the previous_login_at claim set by AuthService.generate_access_token()."""

    async def _claims(self, **kwargs):
        from lys.apps.user_auth.modules.auth.services import AuthService

        store = Mock()
        store.create = AsyncMock(return_value="token-1")
        with patch.object(AuthService, "auth_utils", create=True) as mock_utils, \
             patch.object(AuthService, "generate_access_claims",
                          new_callable=AsyncMock, return_value={"sub": "user-1"}), \
             patch.object(AuthService, "_require_access_token_store", return_value=store):
            mock_utils.config = {"access_token_expire_minutes": 15}
            _, claims = await AuthService.generate_access_token(Mock(), AsyncMock(), **kwargs)
        store.create.assert_awaited_once()
        assert store.create.call_args.args[0] is claims
        return claims

    @pytest.mark.asyncio
    async def test_claim_is_iso_8601(self):
        from datetime import datetime, timezone
        previous = datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)
        claims = await self._claims(previous_login_at=previous)
        assert claims["previous_login_at"] == "2026-10-01T08:30:00+00:00"

    @pytest.mark.asyncio
    async def test_claim_is_null_on_a_first_login(self):
        claims = await self._claims()
        assert claims["previous_login_at"] is None
