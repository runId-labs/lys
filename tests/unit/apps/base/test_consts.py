"""
Unit tests for base app CORS constants.

Tests that all CORS plugin constants are properly defined.
"""

import pytest


class TestCORSPluginConstants:
    """Tests for CORS plugin configuration constants."""

    def test_cors_plugin_key(self):
        """Test CORS_PLUGIN_KEY is defined."""
        from lys.apps.base.consts import CORS_PLUGIN_KEY

        assert CORS_PLUGIN_KEY == "CORS"

    def test_cors_plugin_allow_origins_key(self):
        """Test CORS_PLUGIN_ALLOW_ORIGINS_KEY is defined."""
        from lys.apps.base.consts import CORS_PLUGIN_ALLOW_ORIGINS_KEY

        assert CORS_PLUGIN_ALLOW_ORIGINS_KEY == "allow_origins"

    def test_cors_plugin_allow_methods_key(self):
        """Test CORS_PLUGIN_ALLOW_METHODS_KEY is defined."""
        from lys.apps.base.consts import CORS_PLUGIN_ALLOW_METHODS_KEY

        assert CORS_PLUGIN_ALLOW_METHODS_KEY == "allow_methods"

    def test_cors_plugin_allow_headers_key(self):
        """Test CORS_PLUGIN_ALLOW_HEADERS_KEY is defined."""
        from lys.apps.base.consts import CORS_PLUGIN_ALLOW_HEADERS_KEY

        assert CORS_PLUGIN_ALLOW_HEADERS_KEY == "allow_headers"

    def test_cors_plugin_allow_credentials_key(self):
        """Test CORS_PLUGIN_ALLOW_CREDENTIALS_KEY is defined."""
        from lys.apps.base.consts import CORS_PLUGIN_ALLOW_CREDENTIALS_KEY

        assert CORS_PLUGIN_ALLOW_CREDENTIALS_KEY == "allow_credentials"


class TestCORSConstantsConsistency:
    """Tests for CORS constants consistency."""

    def test_all_cors_keys_are_strings(self):
        """Test that all CORS keys are strings."""
        from lys.apps.base import consts

        cors_keys = [
            "CORS_PLUGIN_KEY",
            "CORS_PLUGIN_ALLOW_ORIGINS_KEY",
            "CORS_PLUGIN_ALLOW_METHODS_KEY",
            "CORS_PLUGIN_ALLOW_HEADERS_KEY",
            "CORS_PLUGIN_ALLOW_CREDENTIALS_KEY",
        ]

        for key in cors_keys:
            value = getattr(consts, key)
            assert isinstance(value, str), f"{key} should be a string"

    def test_cors_keys_are_lowercase_except_plugin(self):
        """Test that CORS setting keys are lowercase (for config consistency)."""
        from lys.apps.base.consts import (
            CORS_PLUGIN_ALLOW_ORIGINS_KEY,
            CORS_PLUGIN_ALLOW_METHODS_KEY,
            CORS_PLUGIN_ALLOW_HEADERS_KEY,
            CORS_PLUGIN_ALLOW_CREDENTIALS_KEY,
        )

        # These should be lowercase for FastAPI CORS middleware compatibility
        assert CORS_PLUGIN_ALLOW_ORIGINS_KEY == CORS_PLUGIN_ALLOW_ORIGINS_KEY.lower()
        assert CORS_PLUGIN_ALLOW_METHODS_KEY == CORS_PLUGIN_ALLOW_METHODS_KEY.lower()
        assert CORS_PLUGIN_ALLOW_HEADERS_KEY == CORS_PLUGIN_ALLOW_HEADERS_KEY.lower()
        assert CORS_PLUGIN_ALLOW_CREDENTIALS_KEY == CORS_PLUGIN_ALLOW_CREDENTIALS_KEY.lower()
