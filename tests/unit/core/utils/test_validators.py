"""
Unit tests for core utils validators module.

Tests validation functions.
"""

import pytest
import uuid


class TestValidateName:
    """Tests for validate_name function."""

    def test_function_exists(self):
        """Test validate_name function exists."""
        from lys.core.utils.validators import validate_name
        assert validate_name is not None
        assert callable(validate_name)

    def test_returns_none_for_none_input(self):
        """Test validate_name returns None for None input."""
        from lys.core.utils.validators import validate_name
        result = validate_name(None, "first_name")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Test validate_name returns None for empty string."""
        from lys.core.utils.validators import validate_name
        result = validate_name("", "first_name")
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Test validate_name returns None for whitespace only."""
        from lys.core.utils.validators import validate_name
        result = validate_name("   ", "first_name")
        assert result is None

    def test_strips_whitespace(self):
        """Test validate_name strips whitespace."""
        from lys.core.utils.validators import validate_name
        result = validate_name("  John  ", "first_name")
        assert result == "John"

    def test_accepts_valid_name(self):
        """Test validate_name accepts valid names."""
        from lys.core.utils.validators import validate_name
        result = validate_name("John", "first_name")
        assert result == "John"

    def test_accepts_name_with_hyphen(self):
        """Test validate_name accepts names with hyphens."""
        from lys.core.utils.validators import validate_name
        result = validate_name("Jean-Pierre", "first_name")
        assert result == "Jean-Pierre"

    def test_accepts_name_with_apostrophe(self):
        """Test validate_name accepts names with apostrophes."""
        from lys.core.utils.validators import validate_name
        result = validate_name("O'Brien", "last_name")
        assert result == "O'Brien"

    def test_accepts_name_with_accents(self):
        """Test validate_name accepts names with accents."""
        from lys.core.utils.validators import validate_name
        result = validate_name("François", "first_name")
        assert result == "François"

    def test_accepts_name_with_spaces(self):
        """Test validate_name accepts names with spaces."""
        from lys.core.utils.validators import validate_name
        result = validate_name("Mary Jane", "first_name")
        assert result == "Mary Jane"

    def test_raises_on_invalid_characters(self):
        """Test validate_name raises on invalid characters."""
        from lys.core.utils.validators import validate_name
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_name("John123", "first_name")

    def test_raises_on_special_characters(self):
        """Test validate_name raises on special characters."""
        from lys.core.utils.validators import validate_name
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_name("John@Doe", "first_name")


class TestValidateLanguageFormat:
    """Tests for validate_language_format function."""

    def test_function_exists(self):
        """Test validate_language_format function exists."""
        from lys.core.utils.validators import validate_language_format
        assert validate_language_format is not None
        assert callable(validate_language_format)

    def test_raises_on_none_input(self):
        """Test validate_language_format raises on None input."""
        from lys.core.utils.validators import validate_language_format
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_language_format(None)

    def test_raises_on_empty_string(self):
        """Test validate_language_format raises on empty string."""
        from lys.core.utils.validators import validate_language_format
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_language_format("")

    def test_accepts_two_letter_code(self):
        """Test validate_language_format accepts two-letter codes."""
        from lys.core.utils.validators import validate_language_format
        result = validate_language_format("en")
        assert result == "en"

    def test_accepts_five_letter_code(self):
        """Test validate_language_format accepts five-letter codes like en-us."""
        from lys.core.utils.validators import validate_language_format
        result = validate_language_format("en-us")
        assert result == "en-us"

    def test_normalizes_to_lowercase(self):
        """Test validate_language_format normalizes to lowercase."""
        from lys.core.utils.validators import validate_language_format
        result = validate_language_format("EN")
        assert result == "en"

    def test_strips_whitespace(self):
        """Test validate_language_format strips whitespace."""
        from lys.core.utils.validators import validate_language_format
        result = validate_language_format("  fr  ")
        assert result == "fr"

    def test_raises_on_invalid_format(self):
        """Test validate_language_format raises on invalid format."""
        from lys.core.utils.validators import validate_language_format
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_language_format("english")

    def test_raises_on_single_letter(self):
        """Test validate_language_format raises on single letter."""
        from lys.core.utils.validators import validate_language_format
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_language_format("e")


class TestValidatePasswordForCreation:
    """Tests for validate_password_for_creation function."""

    def test_function_exists(self):
        """Test validate_password_for_creation function exists."""
        from lys.core.utils.validators import validate_password_for_creation
        assert validate_password_for_creation is not None
        assert callable(validate_password_for_creation)

    def test_raises_on_none_input(self):
        """Test validate_password_for_creation raises on None input."""
        from lys.core.utils.validators import validate_password_for_creation
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_creation(None)

    def test_raises_on_empty_string(self):
        """Test validate_password_for_creation raises on empty string."""
        from lys.core.utils.validators import validate_password_for_creation
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_creation("")

    def test_raises_on_whitespace_only(self):
        """Test validate_password_for_creation raises on whitespace only."""
        from lys.core.utils.validators import validate_password_for_creation
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_creation("   ")

    def test_raises_on_short_password(self):
        """Test validate_password_for_creation raises on password shorter than 8 chars."""
        from lys.core.utils.validators import validate_password_for_creation
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_creation("Pass1")

    def test_raises_on_password_without_letter(self):
        """Test validate_password_for_creation raises on password without letter."""
        from lys.core.utils.validators import validate_password_for_creation
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_creation("12345678")

    def test_raises_on_password_without_digit(self):
        """Test validate_password_for_creation raises on password without digit."""
        from lys.core.utils.validators import validate_password_for_creation
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_creation("Password")

    def test_accepts_valid_password(self):
        """Test validate_password_for_creation accepts valid password."""
        from lys.core.utils.validators import validate_password_for_creation
        result = validate_password_for_creation("Password1")
        assert result == "Password1"

    def test_strips_whitespace(self):
        """Test validate_password_for_creation strips whitespace."""
        from lys.core.utils.validators import validate_password_for_creation
        result = validate_password_for_creation("  Password1  ")
        assert result == "Password1"


class TestValidatePasswordForLogin:
    """Tests for validate_password_for_login function."""

    def test_function_exists(self):
        """Test validate_password_for_login function exists."""
        from lys.core.utils.validators import validate_password_for_login
        assert validate_password_for_login is not None
        assert callable(validate_password_for_login)

    def test_raises_on_none_input(self):
        """Test validate_password_for_login raises on None input."""
        from lys.core.utils.validators import validate_password_for_login
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_login(None)

    def test_raises_on_empty_string(self):
        """Test validate_password_for_login raises on empty string."""
        from lys.core.utils.validators import validate_password_for_login
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_login("")

    def test_raises_on_whitespace_only(self):
        """Test validate_password_for_login raises on whitespace only."""
        from lys.core.utils.validators import validate_password_for_login
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_password_for_login("   ")

    def test_accepts_any_non_empty_password(self):
        """Test validate_password_for_login accepts any non-empty password."""
        from lys.core.utils.validators import validate_password_for_login
        result = validate_password_for_login("a")
        assert result == "a"

    def test_strips_whitespace(self):
        """Test validate_password_for_login strips whitespace."""
        from lys.core.utils.validators import validate_password_for_login
        result = validate_password_for_login("  password  ")
        assert result == "password"


class TestValidateGenderCode:
    """Tests for validate_gender_code function."""

    def test_function_exists(self):
        """Test validate_gender_code function exists."""
        from lys.core.utils.validators import validate_gender_code
        assert validate_gender_code is not None
        assert callable(validate_gender_code)

    def test_returns_none_for_none_input(self):
        """Test validate_gender_code returns None for None input."""
        from lys.core.utils.validators import validate_gender_code
        result = validate_gender_code(None)
        assert result is None

    def test_accepts_valid_gender_codes(self):
        """Test validate_gender_code accepts valid gender codes."""
        from lys.core.utils.validators import validate_gender_code
        from lys.apps.user_auth.modules.user.consts import MALE_GENDER, FEMALE_GENDER, OTHER_GENDER

        assert validate_gender_code(MALE_GENDER) == MALE_GENDER
        assert validate_gender_code(FEMALE_GENDER) == FEMALE_GENDER
        assert validate_gender_code(OTHER_GENDER) == OTHER_GENDER

    def test_raises_on_invalid_gender_code(self):
        """Test validate_gender_code raises on invalid gender code."""
        from lys.core.utils.validators import validate_gender_code
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_gender_code("INVALID")


class TestValidateUuid:
    """Tests for validate_uuid function."""

    def test_function_exists(self):
        """Test validate_uuid function exists."""
        from lys.core.utils.validators import validate_uuid
        assert validate_uuid is not None
        assert callable(validate_uuid)

    def test_accepts_valid_uuid(self):
        """Test validate_uuid accepts valid UUID."""
        from lys.core.utils.validators import validate_uuid
        valid_uuid = str(uuid.uuid4())
        # Should not raise
        validate_uuid(valid_uuid)

    def test_accepts_uuid_object(self):
        """Test validate_uuid accepts UUID object."""
        from lys.core.utils.validators import validate_uuid
        uuid_obj = uuid.uuid4()
        # Should not raise
        validate_uuid(str(uuid_obj))

    def test_raises_on_invalid_uuid(self):
        """Test validate_uuid raises on invalid UUID."""
        from lys.core.utils.validators import validate_uuid
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_uuid("not-a-uuid")

    def test_raises_on_empty_string(self):
        """Test validate_uuid raises on empty string."""
        from lys.core.utils.validators import validate_uuid
        from lys.core.errors import LysError
        with pytest.raises(LysError):
            validate_uuid("")

    def test_raises_with_custom_error(self):
        """Test validate_uuid raises with custom error tuple."""
        from lys.core.utils.validators import validate_uuid
        from lys.core.errors import LysError
        custom_error = (400, "CUSTOM_UUID_ERROR")
        with pytest.raises(LysError) as exc_info:
            validate_uuid("invalid", error=custom_error)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "CUSTOM_UUID_ERROR"


class TestValidateRedirectUrl:
    """Tests for validate_redirect_url function."""

    def test_accepts_valid_https_url(self):
        from lys.core.utils.validators import validate_redirect_url
        validate_redirect_url("https://example.com/callback")

    def test_rejects_http_url(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("http://example.com/callback")

    def test_rejects_no_scheme(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("example.com/callback")

    def test_rejects_no_hostname(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://")

    def test_rejects_private_ip(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://192.168.1.1/callback")

    def test_rejects_loopback_ip(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://127.0.0.1/callback")

    def test_rejects_link_local_ip(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://169.254.169.254/metadata")

    def test_rejects_localhost(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://localhost/callback")

    def test_rejects_metadata_google_internal(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://metadata.google.internal/computeMetadata")

    def test_allowed_domains_accepts_exact_match(self):
        from lys.core.utils.validators import validate_redirect_url
        validate_redirect_url("https://myapp.com/success", allowed_domains=["myapp.com"])

    def test_allowed_domains_accepts_subdomain(self):
        from lys.core.utils.validators import validate_redirect_url
        validate_redirect_url("https://pay.myapp.com/success", allowed_domains=["myapp.com"])

    def test_allowed_domains_rejects_non_matching(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://evil.com/phishing", allowed_domains=["myapp.com"])

    def test_allowed_domains_none_accepts_any_valid(self):
        from lys.core.utils.validators import validate_redirect_url
        validate_redirect_url("https://any-domain.com/callback", allowed_domains=None)

    def test_allowed_domains_bypasses_localhost_block(self):
        """Whitelisted localhost is accepted (dev environment)."""
        from lys.core.utils.validators import validate_redirect_url
        result = validate_redirect_url("https://localhost:5173/callback", allowed_domains=["localhost"])
        assert result == "https://localhost:5173/callback"

    def test_allowed_domains_bypasses_private_ip_block(self):
        """Whitelisted private IP domain is accepted."""
        from lys.core.utils.validators import validate_redirect_url
        result = validate_redirect_url("https://192.168.1.1/callback", allowed_domains=["192.168.1.1"])
        assert result == "https://192.168.1.1/callback"

    def test_rejects_zero_ip(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("https://0.0.0.0/callback")

    def test_accepts_url_with_path_and_query(self):
        from lys.core.utils.validators import validate_redirect_url
        validate_redirect_url("https://example.com/callback?session=abc&status=ok")

    def test_rejects_ftp_scheme(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("ftp://example.com/file")

    def test_rejects_javascript_scheme(self):
        from lys.core.utils.validators import validate_redirect_url
        from lys.core.errors import LysError
        with pytest.raises(LysError, match="UNSAFE_URL"):
            validate_redirect_url("javascript:alert(1)")


class TestValidatorConstants:
    """Tests for validator constants."""

    def test_name_pattern_exists(self):
        """Test NAME_PATTERN constant exists."""
        from lys.core.utils.validators import NAME_PATTERN
        assert NAME_PATTERN is not None

    def test_language_pattern_exists(self):
        """Test LANGUAGE_PATTERN constant exists."""
        from lys.core.utils.validators import LANGUAGE_PATTERN
        assert LANGUAGE_PATTERN is not None

    def test_password_min_length_exists(self):
        """Test PASSWORD_MIN_LENGTH constant exists."""
        from lys.core.utils.validators import PASSWORD_MIN_LENGTH
        assert PASSWORD_MIN_LENGTH is not None
        assert PASSWORD_MIN_LENGTH == 8

    def test_password_max_length_exists(self):
        """Test PASSWORD_MAX_LENGTH constant exists."""
        from lys.core.utils.validators import PASSWORD_MAX_LENGTH
        assert PASSWORD_MAX_LENGTH is not None
        assert PASSWORD_MAX_LENGTH == 128

    def test_valid_gender_codes_exists(self):
        """Test VALID_GENDER_CODES constant exists."""
        from lys.core.utils.validators import VALID_GENDER_CODES
        assert VALID_GENDER_CODES is not None
        assert isinstance(VALID_GENDER_CODES, list)
