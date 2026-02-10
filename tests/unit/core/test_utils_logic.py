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
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret-key")
        token = utils.generate_token("my-service")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_decodable(self):
        """Test generated token can be decoded."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret-key")
        token = utils.generate_token("my-service", expiration_minutes=5)
        decoded = utils.decode_token(token)

        assert decoded["service_name"] == "my-service"
        assert decoded["type"] == "service"

    def test_decode_token_wrong_secret_raises(self):
        """Test decoding with wrong secret raises error."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils1 = ServiceAuthUtils("secret-1")
        utils2 = ServiceAuthUtils("secret-2")

        token = utils1.generate_token("my-service")

        with pytest.raises(Exception):
            utils2.decode_token(token)

    def test_generate_token_includes_iss_and_aud(self):
        """Test generated token includes iss and aud claims."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret")
        token = utils.generate_token("my-service")
        decoded = jwt.decode(
            token, "test-secret", algorithms=["HS256"],
            audience="lys-internal",
        )

        assert decoded["iss"] == "my-service"
        assert decoded["aud"] == "lys-internal"

    def test_decode_token_wrong_type_raises(self):
        """Test decoding a non-service token raises InvalidTokenError."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret")
        # Manually create token with wrong type but correct audience
        payload = {"type": "user", "sub": "user-123", "aud": "lys-internal"}
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            utils.decode_token(token)

    def test_decode_token_wrong_audience_raises(self):
        """Test decoding a token with wrong audience raises error."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret")
        # Token with user audience instead of internal
        payload = {"type": "service", "service_name": "test", "aud": "lys-api"}
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        with pytest.raises(Exception):
            utils.decode_token(token)

    def test_generate_token_with_custom_expiration(self):
        """Test generate_token respects expiration_minutes."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret")
        token = utils.generate_token("my-service", expiration_minutes=10)
        decoded = jwt.decode(
            token, "test-secret", algorithms=["HS256"],
            audience="lys-internal",
        )

        assert "exp" in decoded
        assert "iat" in decoded

    def test_generate_token_includes_instance_id(self):
        """Test generated token includes auto-generated instance_id."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret")
        token = utils.generate_token("my-service")
        decoded = utils.decode_token(token)

        assert "instance_id" in decoded
        assert len(decoded["instance_id"]) == 8

    def test_custom_instance_id(self):
        """Test instance_id can be explicitly set."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret", instance_id="node-42")
        token = utils.generate_token("my-service")
        decoded = utils.decode_token(token)

        assert decoded["instance_id"] == "node-42"

    def test_auto_generated_instance_id_is_stable(self):
        """Test auto-generated instance_id stays the same across multiple tokens."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils = ServiceAuthUtils("test-secret")
        token1 = utils.generate_token("my-service")
        token2 = utils.generate_token("my-service")
        decoded1 = utils.decode_token(token1)
        decoded2 = utils.decode_token(token2)

        assert decoded1["instance_id"] == decoded2["instance_id"]

    def test_different_instances_have_different_ids(self):
        """Test two instances get different auto-generated instance_ids."""
        from lys.core.utils.auth import ServiceAuthUtils

        utils1 = ServiceAuthUtils("test-secret")
        utils2 = ServiceAuthUtils("test-secret")

        assert utils1.instance_id != utils2.instance_id


class TestNowUtc:
    """Test datetime utility."""

    def test_now_utc_returns_aware_datetime(self):
        """Test now_utc returns timezone-aware UTC datetime."""
        from lys.core.utils.datetime import now_utc

        result = now_utc()

        assert isinstance(result, datetime)
        assert result.tzinfo is not None
