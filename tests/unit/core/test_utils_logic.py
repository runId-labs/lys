"""
Unit tests for core utility modules.

Tests cover:
- AuthUtils (core): generate_token, decode_token
- datetime utils: now_utc
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

import jwt
from jwt import InvalidTokenError, ExpiredSignatureError


class TestCoreAuthUtils:
    """Test core AuthUtils (service-to-service)."""

    def test_generate_token_returns_string(self):
        """Test generate_token returns a non-empty JWT string."""
        from lys.core.utils.auth import AuthUtils

        utils = AuthUtils("test-secret-key")
        token = utils.generate_token("my-service")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_decodable(self):
        """Test generated token can be decoded."""
        from lys.core.utils.auth import AuthUtils

        utils = AuthUtils("test-secret-key")
        token = utils.generate_token("my-service", expiration_minutes=5)
        decoded = utils.decode_token(token)

        assert decoded["service_name"] == "my-service"
        assert decoded["type"] == "service"

    def test_decode_token_wrong_secret_raises(self):
        """Test decoding with wrong secret raises error."""
        from lys.core.utils.auth import AuthUtils

        utils1 = AuthUtils("secret-1")
        utils2 = AuthUtils("secret-2")

        token = utils1.generate_token("my-service")

        with pytest.raises(Exception):
            utils2.decode_token(token)

    def test_decode_token_wrong_type_raises(self):
        """Test decoding a non-service token raises InvalidTokenError."""
        from lys.core.utils.auth import AuthUtils

        utils = AuthUtils("test-secret")
        # Manually create token with wrong type
        payload = {"type": "user", "sub": "user-123"}
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            utils.decode_token(token)

    def test_generate_token_with_custom_expiration(self):
        """Test generate_token respects expiration_minutes."""
        from lys.core.utils.auth import AuthUtils

        utils = AuthUtils("test-secret")
        token = utils.generate_token("my-service", expiration_minutes=10)
        decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])

        assert "exp" in decoded
        assert "iat" in decoded
        # Expiry should be ~10 min after iat
        assert decoded["exp"] - decoded["iat"] == 600


class TestNowUtc:
    """Test datetime utility."""

    def test_now_utc_returns_aware_datetime(self):
        """Test now_utc returns timezone-aware UTC datetime."""
        from lys.core.utils.datetime import now_utc

        result = now_utc()

        assert isinstance(result, datetime)
        assert result.tzinfo is not None
