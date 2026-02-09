"""
Unit tests for AuthService logic (_get_lockout_duration, generate_xsrf_token,
set_auth_cookies, clear_auth_cookies).

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
        assert mock_response.delete_cookie.call_count == 2
        deleted_keys = [c[1].get("key", c[0][0]) for c in mock_response.delete_cookie.call_args_list]
        assert "refresh_token" in deleted_keys
        assert "access_token" in deleted_keys
