"""
Unit tests for string utility functions.
"""

import pytest

from lys.core.utils.strings import to_camel_case, to_snake_case


class TestToCamelCase:
    """Tests for to_camel_case function."""

    def test_simple_snake_case(self):
        """Test converting simple snake_case to camelCase."""
        assert to_camel_case("user_name") == "userName"

    def test_multiple_underscores(self):
        """Test converting snake_case with multiple words."""
        assert to_camel_case("get_user_by_id") == "getUserById"

    def test_single_word(self):
        """Test that single word stays lowercase."""
        assert to_camel_case("user") == "user"

    def test_already_camel_case(self):
        """Test that camelCase input is handled (no underscores)."""
        assert to_camel_case("userName") == "userName"

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert to_camel_case("") == ""

    def test_leading_underscore(self):
        """Test string with leading underscore."""
        assert to_camel_case("_private_var") == "PrivateVar"

    def test_trailing_underscore(self):
        """Test string with trailing underscore."""
        assert to_camel_case("var_") == "var"

    def test_consecutive_underscores(self):
        """Test string with consecutive underscores."""
        assert to_camel_case("some__value") == "someValue"

    def test_all_caps_words(self):
        """Test that capitalized words are handled."""
        assert to_camel_case("http_response") == "httpResponse"

    def test_numbers_in_string(self):
        """Test string with numbers."""
        assert to_camel_case("user_id_123") == "userId123"


class TestToSnakeCase:
    """Tests for to_snake_case function."""

    def test_simple_camel_case(self):
        """Test converting simple camelCase to snake_case."""
        assert to_snake_case("userName") == "user_name"

    def test_multiple_capitals(self):
        """Test converting camelCase with multiple capital letters."""
        assert to_snake_case("getUserById") == "get_user_by_id"

    def test_single_word(self):
        """Test that single lowercase word stays the same."""
        assert to_snake_case("user") == "user"

    def test_already_snake_case(self):
        """Test that snake_case input is handled (already lowercase)."""
        assert to_snake_case("user_name") == "user_name"

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert to_snake_case("") == ""

    def test_starts_with_capital(self):
        """Test string starting with capital letter."""
        assert to_snake_case("UserName") == "user_name"

    def test_all_caps(self):
        """Test all caps string."""
        assert to_snake_case("ID") == "i_d"

    def test_consecutive_caps(self):
        """Test consecutive capital letters (acronyms)."""
        assert to_snake_case("getHTTPResponse") == "get_h_t_t_p_response"

    def test_numbers_in_string(self):
        """Test string with numbers."""
        assert to_snake_case("userId123") == "user_id123"

    def test_single_letter(self):
        """Test single letter."""
        assert to_snake_case("A") == "a"


class TestRoundTrip:
    """Tests for round-trip conversions."""

    def test_snake_to_camel_to_snake(self):
        """Test that snake -> camel -> snake preserves original."""
        original = "user_name"
        camel = to_camel_case(original)
        back = to_snake_case(camel)
        assert back == original

    def test_camel_to_snake_to_camel(self):
        """Test that camel -> snake -> camel preserves original."""
        original = "userName"
        snake = to_snake_case(original)
        back = to_camel_case(snake)
        assert back == original

    def test_complex_round_trip(self):
        """Test round-trip with complex name."""
        original = "get_user_by_email_address"
        camel = to_camel_case(original)
        back = to_snake_case(camel)
        assert back == original
