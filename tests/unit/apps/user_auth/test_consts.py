"""
Unit tests for user_auth constants.

Tests that all required constants are defined with expected values.
"""

import pytest


class TestAuthPluginConstants:
    """Tests for authentication plugin constants."""

    def test_auth_plugin_key(self):
        """Test AUTH_PLUGIN_KEY is defined."""
        from lys.apps.user_auth.consts import AUTH_PLUGIN_KEY

        assert AUTH_PLUGIN_KEY == "auth"

    def test_check_xsrf_token_key(self):
        """Test AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY is defined."""
        from lys.apps.user_auth.consts import AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY

        assert AUTH_PLUGIN_CHECK_XSRF_TOKEN_KEY == "check_xsrf_token"


class TestAccessConstants:
    """Tests for access-related constants."""

    def test_owner_access_key(self):
        """Test OWNER_ACCESS_KEY is defined."""
        from lys.apps.user_auth.consts import OWNER_ACCESS_KEY

        assert OWNER_ACCESS_KEY == "owner"


class TestCookieConstants:
    """Tests for cookie-related constants."""

    def test_access_cookie_key(self):
        """Test ACCESS_COOKIE_KEY is defined."""
        from lys.apps.user_auth.consts import ACCESS_COOKIE_KEY

        assert ACCESS_COOKIE_KEY == "access_token"

    def test_refresh_cookie_key(self):
        """Test REFRESH_COOKIE_KEY is defined."""
        from lys.apps.user_auth.consts import REFRESH_COOKIE_KEY

        assert REFRESH_COOKIE_KEY == "refresh_token"


class TestRequestHeaderConstants:
    """Tests for request header constants."""

    def test_xsrf_token_header_key(self):
        """Test REQUEST_HEADER_XSRF_TOKEN_KEY is defined."""
        from lys.apps.user_auth.consts import REQUEST_HEADER_XSRF_TOKEN_KEY

        assert REQUEST_HEADER_XSRF_TOKEN_KEY == "x-xsrf-token"
