"""
Unit tests for user_auth utilities.

Tests AuthUtils class for password hashing, JWT encoding/decoding,
and XSRF token generation.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import bcrypt
import jwt


class TestAuthUtilsHashPassword:
    """Tests for AuthUtils.hash_password static method."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        from lys.apps.user_auth.utils import AuthUtils

        result = AuthUtils.hash_password("test_password")

        assert isinstance(result, str)

    def test_hash_password_is_bcrypt_hash(self):
        """Test that the hash is a valid bcrypt hash."""
        from lys.apps.user_auth.utils import AuthUtils

        result = AuthUtils.hash_password("test_password")

        # bcrypt hashes start with $2b$ or $2a$
        assert result.startswith("$2")
        assert len(result) == 60  # bcrypt hash length

    def test_hash_password_different_for_same_input(self):
        """Test that hashing same password twice produces different results (salt)."""
        from lys.apps.user_auth.utils import AuthUtils

        hash1 = AuthUtils.hash_password("same_password")
        hash2 = AuthUtils.hash_password("same_password")

        assert hash1 != hash2  # Different salts

    def test_hash_password_verifiable(self):
        """Test that hashed password can be verified with bcrypt."""
        from lys.apps.user_auth.utils import AuthUtils

        password = "my_secure_password"
        hashed = AuthUtils.hash_password(password)

        # Verify using bcrypt
        is_valid = bcrypt.checkpw(
            password.encode('utf-8'),
            hashed.encode('utf-8')
        )
        assert is_valid is True

    def test_hash_password_wrong_password_fails_verification(self):
        """Test that wrong password fails verification."""
        from lys.apps.user_auth.utils import AuthUtils

        hashed = AuthUtils.hash_password("correct_password")

        is_valid = bcrypt.checkpw(
            "wrong_password".encode('utf-8'),
            hashed.encode('utf-8')
        )
        assert is_valid is False

    def test_hash_password_handles_unicode(self):
        """Test that hash_password handles unicode characters."""
        from lys.apps.user_auth.utils import AuthUtils

        password = "motdepasse_éàü_日本語"
        hashed = AuthUtils.hash_password(password)

        assert isinstance(hashed, str)
        is_valid = bcrypt.checkpw(
            password.encode('utf-8'),
            hashed.encode('utf-8')
        )
        assert is_valid is True

    def test_hash_password_handles_empty_string(self):
        """Test that hash_password handles empty string."""
        from lys.apps.user_auth.utils import AuthUtils

        hashed = AuthUtils.hash_password("")

        assert isinstance(hashed, str)
        assert len(hashed) == 60


class TestAuthUtilsGenerateXsrfToken:
    """Tests for AuthUtils.generate_xsrf_token static method."""

    @pytest.mark.asyncio
    async def test_generate_xsrf_token_returns_bytes(self):
        """Test that generate_xsrf_token returns bytes."""
        from lys.apps.user_auth.utils import AuthUtils

        result = await AuthUtils.generate_xsrf_token()

        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_generate_xsrf_token_is_hex(self):
        """Test that token is valid hex string encoded as ASCII."""
        from lys.apps.user_auth.utils import AuthUtils

        result = await AuthUtils.generate_xsrf_token()

        # Should be decodable as ASCII
        decoded = result.decode('ascii')
        # Should be valid hex (128 chars for 64 bytes)
        assert len(decoded) == 128
        int(decoded, 16)  # Should not raise

    @pytest.mark.asyncio
    async def test_generate_xsrf_token_unique(self):
        """Test that each token is unique."""
        from lys.apps.user_auth.utils import AuthUtils

        token1 = await AuthUtils.generate_xsrf_token()
        token2 = await AuthUtils.generate_xsrf_token()

        assert token1 != token2


class TestAuthUtilsValidateConfig:
    """Tests for AuthUtils._validate_auth_config method."""

    @pytest.fixture
    def mock_app_manager(self):
        """Create mock app_manager with settings."""
        app_manager = MagicMock()
        app_manager.settings.secret_key = "test_secret_key_for_jwt_32bytes!"
        app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS256"
        }
        return app_manager

    def test_validate_config_accepts_hs256(self, mock_app_manager):
        """Test that HS256 algorithm is accepted."""
        from lys.apps.user_auth.utils import AuthUtils

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            # Should not raise
            auth_utils = AuthUtils()
            assert auth_utils.config["encryption_algorithm"] == "HS256"

    def test_validate_config_accepts_hs384(self, mock_app_manager):
        """Test that HS384 algorithm is accepted."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = "a" * 48
        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS384"
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            auth_utils = AuthUtils()
            assert auth_utils.config["encryption_algorithm"] == "HS384"

    def test_validate_config_accepts_hs512(self, mock_app_manager):
        """Test that HS512 algorithm is accepted."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = "a" * 64
        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS512"
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            auth_utils = AuthUtils()
            assert auth_utils.config["encryption_algorithm"] == "HS512"

    def test_validate_config_rejects_unsupported_algorithm(self, mock_app_manager):
        """Test that unsupported algorithms are rejected."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "RS256"  # Not in allowed list
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            with pytest.raises(ValueError) as exc_info:
                AuthUtils()

            assert "Unsupported JWT algorithm" in str(exc_info.value)
            assert "RS256" in str(exc_info.value)

    def test_validate_config_rejects_missing_secret_key(self, mock_app_manager):
        """Test that missing secret_key is rejected."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = None

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            with pytest.raises(ValueError) as exc_info:
                AuthUtils()

            assert "secret_key is required" in str(exc_info.value)

    def test_validate_config_handles_empty_config(self, mock_app_manager):
        """Test that empty config uses defaults (with warning)."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.get_plugin_config.return_value = None

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            # Should not raise, just warn
            auth_utils = AuthUtils()
            assert auth_utils.config is None

    def test_validate_config_rejects_short_secret_key(self, mock_app_manager):
        """Test that secret_key shorter than 32 bytes is rejected for HS256."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = "too_short"

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            with pytest.raises(ValueError) as exc_info:
                AuthUtils()
            assert "at least 32 bytes" in str(exc_info.value)

    def test_validate_config_rejects_short_key_for_hs384(self, mock_app_manager):
        """Test that secret_key shorter than 48 bytes is rejected for HS384."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = "a" * 40  # 40 bytes, need 48
        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS384"
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            with pytest.raises(ValueError) as exc_info:
                AuthUtils()
            assert "at least 48 bytes" in str(exc_info.value)

    def test_validate_config_rejects_short_key_for_hs512(self, mock_app_manager):
        """Test that secret_key shorter than 64 bytes is rejected for HS512."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = "a" * 50  # 50 bytes, need 64
        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS512"
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            with pytest.raises(ValueError) as exc_info:
                AuthUtils()
            assert "at least 64 bytes" in str(exc_info.value)

    def test_validate_config_accepts_exact_min_length(self, mock_app_manager):
        """Test that secret_key of exactly 32 bytes is accepted for HS256."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager.settings.secret_key = "a" * 32

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            auth_utils = AuthUtils()
            assert auth_utils.secret_key == "a" * 32


class TestAuthUtilsEncode:
    """Tests for AuthUtils.encode method."""

    @pytest.fixture
    def auth_utils(self):
        """Create AuthUtils instance with mocked app_manager."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager = MagicMock()
        mock_app_manager.settings.secret_key = "test_secret_key_for_jwt_32bytes!"
        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS256"
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            return AuthUtils()

    @pytest.mark.asyncio
    async def test_encode_returns_string(self, auth_utils):
        """Test that encode returns a JWT string."""
        claims = {"sub": "user-123", "name": "Test User"}

        result = await auth_utils.encode(claims)

        assert isinstance(result, str)
        # JWT has 3 parts separated by dots
        assert len(result.split(".")) == 3

    @pytest.mark.asyncio
    async def test_encode_creates_valid_jwt(self, auth_utils):
        """Test that encoded JWT can be decoded."""
        claims = {"sub": "user-123", "role": "admin"}

        token = await auth_utils.encode(claims)

        # Decode manually to verify
        decoded = jwt.decode(
            token,
            "test_secret_key_for_jwt_32bytes!",
            algorithms=["HS256"],
            audience="lys-api",
        )
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "admin"

    @pytest.mark.asyncio
    async def test_encode_injects_iss_and_aud(self, auth_utils):
        """Test that encode injects iss and aud claims."""
        claims = {"sub": "user-123"}

        token = await auth_utils.encode(claims)

        decoded = jwt.decode(
            token,
            "test_secret_key_for_jwt_32bytes!",
            algorithms=["HS256"],
            audience="lys-api",
        )
        assert decoded["iss"] == "lys-auth"
        assert decoded["aud"] == "lys-api"

    @pytest.mark.asyncio
    async def test_encode_with_complex_claims(self, auth_utils):
        """Test encoding complex claims structure."""
        claims = {
            "sub": "user-456",
            "is_super_user": False,
            "webservices": {
                "get_users": "full",
                "update_profile": "owner"
            },
            "organizations": {
                "org-1": {"roles": ["admin"]}
            }
        }

        token = await auth_utils.encode(claims)
        decoded = jwt.decode(
            token,
            "test_secret_key_for_jwt_32bytes!",
            algorithms=["HS256"],
            audience="lys-api",
        )

        assert decoded["webservices"]["get_users"] == "full"
        assert decoded["organizations"]["org-1"]["roles"] == ["admin"]


class TestAuthUtilsDecode:
    """Tests for AuthUtils.decode method."""

    @pytest.fixture
    def auth_utils(self):
        """Create AuthUtils instance with mocked app_manager."""
        from lys.apps.user_auth.utils import AuthUtils

        mock_app_manager = MagicMock()
        mock_app_manager.settings.secret_key = "test_secret_key_for_jwt_32bytes!"
        mock_app_manager.settings.get_plugin_config.return_value = {
            "encryption_algorithm": "HS256"
        }

        with patch.object(AuthUtils, "app_manager", mock_app_manager):
            return AuthUtils()

    @pytest.mark.asyncio
    async def test_decode_returns_claims(self, auth_utils):
        """Test that decode returns the original claims."""
        # Create a valid token with required iss/aud
        token = jwt.encode(
            {"sub": "user-789", "name": "Test", "iss": "lys-auth", "aud": "lys-api"},
            "test_secret_key_for_jwt_32bytes!",
            algorithm="HS256"
        )

        result = await auth_utils.decode(token)

        assert result["sub"] == "user-789"
        assert result["name"] == "Test"

    @pytest.mark.asyncio
    async def test_decode_invalid_token_raises(self, auth_utils):
        """Test that invalid token raises exception."""
        with pytest.raises(jwt.exceptions.DecodeError):
            await auth_utils.decode("invalid.token.here")

    @pytest.mark.asyncio
    async def test_decode_wrong_secret_raises(self, auth_utils):
        """Test that token signed with wrong secret raises exception."""
        token = jwt.encode(
            {"sub": "user-123", "iss": "lys-auth", "aud": "lys-api"},
            "different_secret_key",
            algorithm="HS256"
        )

        with pytest.raises(jwt.exceptions.InvalidSignatureError):
            await auth_utils.decode(token)

    @pytest.mark.asyncio
    async def test_decode_expired_token_raises(self, auth_utils):
        """Test that expired token raises exception."""
        import time

        token = jwt.encode(
            {"sub": "user-123", "exp": int(time.time()) - 3600,
             "iss": "lys-auth", "aud": "lys-api"},
            "test_secret_key_for_jwt_32bytes!",
            algorithm="HS256"
        )

        with pytest.raises(jwt.exceptions.ExpiredSignatureError):
            await auth_utils.decode(token)

    @pytest.mark.asyncio
    async def test_decode_wrong_audience_raises(self, auth_utils):
        """Test that token with wrong audience is rejected."""
        token = jwt.encode(
            {"sub": "user-123", "iss": "lys-auth", "aud": "lys-internal"},
            "test_secret_key_for_jwt_32bytes!",
            algorithm="HS256"
        )

        with pytest.raises(jwt.exceptions.InvalidAudienceError):
            await auth_utils.decode(token)

    @pytest.mark.asyncio
    async def test_decode_wrong_issuer_raises(self, auth_utils):
        """Test that token with wrong issuer is rejected."""
        token = jwt.encode(
            {"sub": "user-123", "iss": "other-service", "aud": "lys-api"},
            "test_secret_key_for_jwt_32bytes!",
            algorithm="HS256"
        )

        with pytest.raises(jwt.exceptions.InvalidIssuerError):
            await auth_utils.decode(token)

    @pytest.mark.asyncio
    async def test_decode_missing_audience_raises(self, auth_utils):
        """Test that token without audience is rejected."""
        token = jwt.encode(
            {"sub": "user-123", "iss": "lys-auth"},
            "test_secret_key_for_jwt_32bytes!",
            algorithm="HS256"
        )

        with pytest.raises(jwt.exceptions.MissingRequiredClaimError):
            await auth_utils.decode(token)

    @pytest.mark.asyncio
    async def test_decode_service_token_rejected(self, auth_utils):
        """Test that a service-to-service token cannot be used as user token."""
        # Service tokens have aud="lys-internal" and iss=service_name
        token = jwt.encode(
            {"type": "service", "service_name": "billing", "iss": "billing", "aud": "lys-internal"},
            "test_secret_key_for_jwt_32bytes!",
            algorithm="HS256"
        )

        # Rejected due to wrong iss or aud (PyJWT checks iss first)
        with pytest.raises((jwt.exceptions.InvalidAudienceError, jwt.exceptions.InvalidIssuerError)):
            await auth_utils.decode(token)

    @pytest.mark.asyncio
    async def test_encode_decode_roundtrip(self, auth_utils):
        """Test that encode then decode returns original claims."""
        original_claims = {
            "sub": "user-roundtrip",
            "email": "test@example.com",
            "roles": ["user", "admin"]
        }

        token = await auth_utils.encode(original_claims)
        decoded = await auth_utils.decode(token)

        assert decoded["sub"] == original_claims["sub"]
        assert decoded["email"] == original_claims["email"]
        assert decoded["roles"] == original_claims["roles"]


class TestAuthUtilsAllowedAlgorithms:
    """Tests for ALLOWED_ALGORITHMS constant."""

    def test_allowed_algorithms_contains_hs256(self):
        """Test that HS256 is in allowed algorithms."""
        from lys.apps.user_auth.utils import AuthUtils

        assert "HS256" in AuthUtils.ALLOWED_ALGORITHMS

    def test_allowed_algorithms_contains_hs384(self):
        """Test that HS384 is in allowed algorithms."""
        from lys.apps.user_auth.utils import AuthUtils

        assert "HS384" in AuthUtils.ALLOWED_ALGORITHMS

    def test_allowed_algorithms_contains_hs512(self):
        """Test that HS512 is in allowed algorithms."""
        from lys.apps.user_auth.utils import AuthUtils

        assert "HS512" in AuthUtils.ALLOWED_ALGORITHMS

    def test_allowed_algorithms_does_not_contain_rs256(self):
        """Test that RS256 is not in allowed algorithms (asymmetric)."""
        from lys.apps.user_auth.utils import AuthUtils

        assert "RS256" not in AuthUtils.ALLOWED_ALGORITHMS
