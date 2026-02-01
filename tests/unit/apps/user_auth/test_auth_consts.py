"""
Unit tests for user_auth auth module constants.

Tests login attempt status constants.
"""

import pytest


class TestLoginAttemptStatusConstants:
    """Tests for login attempt status constants."""

    def test_failed_login_attempt_status(self):
        """Test FAILED_LOGIN_ATTEMPT_STATUS constant."""
        from lys.apps.user_auth.modules.auth.consts import FAILED_LOGIN_ATTEMPT_STATUS
        assert FAILED_LOGIN_ATTEMPT_STATUS == "FAILED"

    def test_succeed_login_attempt_status(self):
        """Test SUCCEED_LOGIN_ATTEMPT_STATUS constant."""
        from lys.apps.user_auth.modules.auth.consts import SUCCEED_LOGIN_ATTEMPT_STATUS
        assert SUCCEED_LOGIN_ATTEMPT_STATUS == "SUCCEED"
