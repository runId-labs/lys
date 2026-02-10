"""
Unit tests for UserDevFixtures.format_password — H6 security fix.

Verifies that dev fixture passwords are randomly generated (not hardcoded)
and that the email is logged for developer convenience.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestFormatPasswordGeneratesRandom:
    """Tests for UserDevFixtures.format_password random generation."""

    @pytest.mark.asyncio
    async def test_ignores_provided_password(self):
        """format_password must ignore the provided password value."""
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures

        with patch.object(UserDevFixtures, "app_manager", create=True):
            with patch("lys.apps.user_auth.modules.user.fixtures.AuthUtils") as mock_auth:
                mock_auth.hash_password.return_value = "$2b$hash"
                await UserDevFixtures.format_password(
                    "password", attributes={"email_address": "a@b.com"}
                )
                # The argument passed to hash_password must NOT be "password"
                actual_arg = mock_auth.hash_password.call_args[0][0]
                assert actual_arg != "password"

    @pytest.mark.asyncio
    async def test_returns_bcrypt_hash(self):
        """format_password must return the bcrypt hash from AuthUtils."""
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures

        with patch.object(UserDevFixtures, "app_manager", create=True):
            with patch("lys.apps.user_auth.modules.user.fixtures.AuthUtils") as mock_auth:
                mock_auth.hash_password.return_value = "$2b$hashed"
                result = await UserDevFixtures.format_password(
                    "password", attributes={"email_address": "x@y.com"}
                )
                assert result == "$2b$hashed"

    @pytest.mark.asyncio
    async def test_generates_unique_passwords(self):
        """Each call must generate a different random password."""
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures

        generated = []
        with patch.object(UserDevFixtures, "app_manager", create=True):
            with patch("lys.apps.user_auth.modules.user.fixtures.AuthUtils") as mock_auth:
                mock_auth.hash_password.side_effect = lambda p: p
                for _ in range(5):
                    result = await UserDevFixtures.format_password(
                        "password", attributes={"email_address": "a@b.com"}
                    )
                    generated.append(result)
        # All values must be unique
        assert len(set(generated)) == 5


class TestFormatPasswordLogsEmail:
    """Tests that format_password logs the email for developer convenience."""

    @pytest.mark.asyncio
    async def test_logs_email_address(self):
        """format_password must log the email from attributes."""
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures

        with patch.object(UserDevFixtures, "app_manager", create=True):
            with patch("lys.apps.user_auth.modules.user.fixtures.AuthUtils") as mock_auth, \
                 patch("lys.apps.user_auth.modules.user.fixtures.logging") as mock_logging:
                mock_auth.hash_password.return_value = "$2b$hash"
                await UserDevFixtures.format_password(
                    "password", attributes={"email_address": "dev@test.fr"}
                )
                mock_logging.info.assert_called_once()
                log_msg = mock_logging.info.call_args[0][0]
                assert "dev@test.fr" in log_msg

    @pytest.mark.asyncio
    async def test_logs_unknown_when_no_email(self):
        """format_password must log 'unknown' when email_address is missing."""
        from lys.apps.user_auth.modules.user.fixtures import UserDevFixtures

        with patch.object(UserDevFixtures, "app_manager", create=True):
            with patch("lys.apps.user_auth.modules.user.fixtures.AuthUtils") as mock_auth, \
                 patch("lys.apps.user_auth.modules.user.fixtures.logging") as mock_logging:
                mock_auth.hash_password.return_value = "$2b$hash"
                await UserDevFixtures.format_password(
                    "password", attributes={}
                )
                log_msg = mock_logging.info.call_args[0][0]
                assert "unknown" in log_msg