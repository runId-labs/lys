"""
Unit tests for user_auth error codes.

Tests that all error codes are properly defined with correct HTTP status codes.
"""

import pytest


class TestValidationErrors:
    """Tests for 400 Bad Request validation errors."""

    def test_empty_login_error(self):
        """Test EMPTY_LOGIN_ERROR is defined with 400 status."""
        from lys.apps.user_auth.errors import EMPTY_LOGIN_ERROR

        assert EMPTY_LOGIN_ERROR == (400, "EMPTY_LOGIN_ERROR")

    def test_empty_password_error(self):
        """Test EMPTY_PASSWORD_ERROR is defined with 400 status."""
        from lys.apps.user_auth.errors import EMPTY_PASSWORD_ERROR

        assert EMPTY_PASSWORD_ERROR == (400, "EMPTY_PASSWORD_ERROR")

    def test_weak_password(self):
        """Test WEAK_PASSWORD is defined with 400 status."""
        from lys.apps.user_auth.errors import WEAK_PASSWORD

        assert WEAK_PASSWORD == (400, "WEAK_PASSWORD")

    def test_invalid_name(self):
        """Test INVALID_NAME is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_NAME

        assert INVALID_NAME == (400, "INVALID_NAME")

    def test_invalid_gender(self):
        """Test INVALID_GENDER is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_GENDER

        assert INVALID_GENDER == (400, "INVALID_GENDER")

    def test_invalid_language(self):
        """Test INVALID_LANGUAGE is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_LANGUAGE

        assert INVALID_LANGUAGE == (400, "INVALID_LANGUAGE")

    def test_invalid_reset_token_error(self):
        """Test INVALID_RESET_TOKEN_ERROR is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_RESET_TOKEN_ERROR

        assert INVALID_RESET_TOKEN_ERROR == (400, "INVALID_RESET_TOKEN_ERROR")

    def test_expired_reset_token_error(self):
        """Test EXPIRED_RESET_TOKEN_ERROR is defined with 400 status."""
        from lys.apps.user_auth.errors import EXPIRED_RESET_TOKEN_ERROR

        assert EXPIRED_RESET_TOKEN_ERROR == (400, "EXPIRED_RESET_TOKEN_ERROR")

    def test_email_already_validated_error(self):
        """Test EMAIL_ALREADY_VALIDATED_ERROR is defined with 400 status."""
        from lys.apps.user_auth.errors import EMAIL_ALREADY_VALIDATED_ERROR

        assert EMAIL_ALREADY_VALIDATED_ERROR == (400, "EMAIL_ALREADY_VALIDATED_ERROR")

    def test_invalid_status_change(self):
        """Test INVALID_STATUS_CHANGE is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_STATUS_CHANGE

        assert INVALID_STATUS_CHANGE == (400, "INVALID_STATUS_CHANGE")

    def test_invalid_user_status(self):
        """Test INVALID_USER_STATUS is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_USER_STATUS

        assert INVALID_USER_STATUS == (400, "INVALID_USER_STATUS")

    def test_invalid_user_id(self):
        """Test INVALID_USER_ID is defined with 400 status."""
        from lys.apps.user_auth.errors import INVALID_USER_ID

        assert INVALID_USER_ID == (400, "INVALID_USER_ID")

    def test_user_already_anonymized(self):
        """Test USER_ALREADY_ANONYMIZED is defined with 400 status."""
        from lys.apps.user_auth.errors import USER_ALREADY_ANONYMIZED

        assert USER_ALREADY_ANONYMIZED == (400, "USER_ALREADY_ANONYMIZED")


class TestAuthenticationErrors:
    """Tests for 401 Unauthorized authentication errors."""

    def test_access_denied_error(self):
        """Test ACCESS_DENIED_ERROR is defined with 401 status."""
        from lys.apps.user_auth.errors import ACCESS_DENIED_ERROR

        assert ACCESS_DENIED_ERROR == (401, "ACCESS_DENIED_ERROR")

    def test_invalid_refresh_token_error(self):
        """Test INVALID_REFRESH_TOKEN_ERROR is defined with 401 status."""
        from lys.apps.user_auth.errors import INVALID_REFRESH_TOKEN_ERROR

        assert INVALID_REFRESH_TOKEN_ERROR == (401, "INVALID_REFRESH_TOKEN_ERROR")

    def test_missing_refresh_token_error(self):
        """Test MISSING_REFRESH_TOKEN_ERROR is defined with 401 status."""
        from lys.apps.user_auth.errors import MISSING_REFRESH_TOKEN_ERROR

        assert MISSING_REFRESH_TOKEN_ERROR == (401, "MISSING_REFRESH_TOKEN_ERROR")

    def test_invalid_credentials_error(self):
        """Test INVALID_CREDENTIALS_ERROR is defined with 401 status."""
        from lys.apps.user_auth.errors import INVALID_CREDENTIALS_ERROR

        assert INVALID_CREDENTIALS_ERROR == (401, "INVALID_CREDENTIALS_ERROR")

    def test_wrong_refresh_token_error(self):
        """Test WRONG_REFRESH_TOKEN_ERROR is defined with 401 status."""
        from lys.apps.user_auth.errors import WRONG_REFRESH_TOKEN_ERROR

        assert WRONG_REFRESH_TOKEN_ERROR == (401, "WRONG_REFRESH_TOKEN_ERROR")


class TestForbiddenErrors:
    """Tests for 403 Forbidden errors."""

    def test_blocked_user_error(self):
        """Test BLOCKED_USER_ERROR is defined with 403 status."""
        from lys.apps.user_auth.errors import BLOCKED_USER_ERROR

        assert BLOCKED_USER_ERROR == (403, "BLOCKED_USER_ERROR")

    def test_invalid_xsrf_token_error(self):
        """Test INVALID_XSRF_TOKEN_ERROR is defined with 403 status."""
        from lys.apps.user_auth.errors import INVALID_XSRF_TOKEN_ERROR

        assert INVALID_XSRF_TOKEN_ERROR == (403, "INVALID_XSRF_TOKEN_ERROR")

    def test_already_connected_error(self):
        """Test ALREADY_CONNECTED_ERROR is defined with 403 status."""
        from lys.apps.user_auth.errors import ALREADY_CONNECTED_ERROR

        assert ALREADY_CONNECTED_ERROR == (403, "ALREADY_CONNECTED_ERROR")


class TestConflictErrors:
    """Tests for 409 Conflict errors."""

    def test_user_already_exists(self):
        """Test USER_ALREADY_EXISTS is defined with 409 status."""
        from lys.apps.user_auth.errors import USER_ALREADY_EXISTS

        assert USER_ALREADY_EXISTS == (409, "USER_ALREADY_EXISTS")


class TestRateLimitErrors:
    """Tests for 429 Too Many Requests errors."""

    def test_rate_limit_error(self):
        """Test RATE_LIMIT_ERROR is defined with 429 status."""
        from lys.apps.user_auth.errors import RATE_LIMIT_ERROR

        assert RATE_LIMIT_ERROR == (429, "RATE_LIMIT_ERROR")


class TestErrorTupleStructure:
    """Tests for error tuple structure consistency."""

    def test_all_errors_are_tuples(self):
        """Test that all errors are tuples with (status_code, error_name)."""
        from lys.apps.user_auth import errors

        error_names = [
            "EMPTY_LOGIN_ERROR", "EMPTY_PASSWORD_ERROR", "WEAK_PASSWORD",
            "INVALID_NAME", "INVALID_GENDER", "INVALID_LANGUAGE",
            "INVALID_RESET_TOKEN_ERROR", "EXPIRED_RESET_TOKEN_ERROR",
            "EMAIL_ALREADY_VALIDATED_ERROR", "INVALID_STATUS_CHANGE",
            "INVALID_USER_STATUS", "INVALID_USER_ID", "USER_ALREADY_ANONYMIZED",
            "ACCESS_DENIED_ERROR", "INVALID_REFRESH_TOKEN_ERROR",
            "MISSING_REFRESH_TOKEN_ERROR", "INVALID_CREDENTIALS_ERROR",
            "WRONG_REFRESH_TOKEN_ERROR", "BLOCKED_USER_ERROR",
            "INVALID_XSRF_TOKEN_ERROR", "ALREADY_CONNECTED_ERROR",
            "USER_ALREADY_EXISTS", "RATE_LIMIT_ERROR"
        ]

        for name in error_names:
            error = getattr(errors, name)
            assert isinstance(error, tuple), f"{name} should be a tuple"
            assert len(error) == 2, f"{name} should have 2 elements"
            assert isinstance(error[0], int), f"{name} status code should be int"
            assert isinstance(error[1], str), f"{name} error name should be str"

    def test_error_codes_are_valid_http_status(self):
        """Test that all error codes are valid HTTP status codes."""
        from lys.apps.user_auth import errors

        valid_status_codes = {400, 401, 403, 409, 429}

        error_names = [
            "EMPTY_LOGIN_ERROR", "ACCESS_DENIED_ERROR", "BLOCKED_USER_ERROR",
            "USER_ALREADY_EXISTS", "RATE_LIMIT_ERROR"
        ]

        for name in error_names:
            error = getattr(errors, name)
            assert error[0] in valid_status_codes, f"{name} has invalid status code {error[0]}"
