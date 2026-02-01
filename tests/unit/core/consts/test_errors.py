"""
Unit tests for core consts errors module.

Tests error tuple constants.
"""

import pytest


class TestErrorConstants:
    """Tests for error constants."""

    def test_not_uuid_error_exists(self):
        """Test NOT_UUID_ERROR is defined."""
        from lys.core.consts.errors import NOT_UUID_ERROR
        assert NOT_UUID_ERROR is not None

    def test_not_uuid_error_is_tuple(self):
        """Test NOT_UUID_ERROR is a tuple."""
        from lys.core.consts.errors import NOT_UUID_ERROR
        assert isinstance(NOT_UUID_ERROR, tuple)

    def test_not_uuid_error_has_code_400(self):
        """Test NOT_UUID_ERROR has status code 400."""
        from lys.core.consts.errors import NOT_UUID_ERROR
        assert NOT_UUID_ERROR[0] == 400

    def test_not_uuid_error_has_message(self):
        """Test NOT_UUID_ERROR has message NOT_UUID."""
        from lys.core.consts.errors import NOT_UUID_ERROR
        assert NOT_UUID_ERROR[1] == "NOT_UUID"

    def test_permission_denied_error_exists(self):
        """Test PERMISSION_DENIED_ERROR is defined."""
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR
        assert PERMISSION_DENIED_ERROR is not None

    def test_permission_denied_error_is_tuple(self):
        """Test PERMISSION_DENIED_ERROR is a tuple."""
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR
        assert isinstance(PERMISSION_DENIED_ERROR, tuple)

    def test_permission_denied_error_has_code_403(self):
        """Test PERMISSION_DENIED_ERROR has status code 403."""
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR
        assert PERMISSION_DENIED_ERROR[0] == 403

    def test_permission_denied_error_has_message(self):
        """Test PERMISSION_DENIED_ERROR has message PERMISSION_DENIED."""
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR
        assert PERMISSION_DENIED_ERROR[1] == "PERMISSION_DENIED"

    def test_not_found_error_exists(self):
        """Test NOT_FOUND_ERROR is defined."""
        from lys.core.consts.errors import NOT_FOUND_ERROR
        assert NOT_FOUND_ERROR is not None

    def test_not_found_error_is_tuple(self):
        """Test NOT_FOUND_ERROR is a tuple."""
        from lys.core.consts.errors import NOT_FOUND_ERROR
        assert isinstance(NOT_FOUND_ERROR, tuple)

    def test_not_found_error_has_code_404(self):
        """Test NOT_FOUND_ERROR has status code 404."""
        from lys.core.consts.errors import NOT_FOUND_ERROR
        assert NOT_FOUND_ERROR[0] == 404

    def test_not_found_error_has_message(self):
        """Test NOT_FOUND_ERROR has message NOT_FOUND."""
        from lys.core.consts.errors import NOT_FOUND_ERROR
        assert NOT_FOUND_ERROR[1] == "NOT_FOUND"

    def test_unknown_webservice_error_exists(self):
        """Test UNKNOWN_WEBSERVICE_ERROR is defined."""
        from lys.core.consts.errors import UNKNOWN_WEBSERVICE_ERROR
        assert UNKNOWN_WEBSERVICE_ERROR is not None

    def test_unknown_webservice_error_is_tuple(self):
        """Test UNKNOWN_WEBSERVICE_ERROR is a tuple."""
        from lys.core.consts.errors import UNKNOWN_WEBSERVICE_ERROR
        assert isinstance(UNKNOWN_WEBSERVICE_ERROR, tuple)

    def test_unknown_webservice_error_has_code_404(self):
        """Test UNKNOWN_WEBSERVICE_ERROR has status code 404."""
        from lys.core.consts.errors import UNKNOWN_WEBSERVICE_ERROR
        assert UNKNOWN_WEBSERVICE_ERROR[0] == 404

    def test_unknown_webservice_error_has_message(self):
        """Test UNKNOWN_WEBSERVICE_ERROR has message UNKNOWN_WEBSERVICE."""
        from lys.core.consts.errors import UNKNOWN_WEBSERVICE_ERROR
        assert UNKNOWN_WEBSERVICE_ERROR[1] == "UNKNOWN_WEBSERVICE"


class TestErrorConstantsConsistency:
    """Tests for error constants consistency."""

    def test_all_errors_are_tuples_of_two(self):
        """Test all error constants are tuples of 2 elements."""
        from lys.core.consts import errors

        error_constants = [
            errors.NOT_UUID_ERROR,
            errors.PERMISSION_DENIED_ERROR,
            errors.NOT_FOUND_ERROR,
            errors.UNKNOWN_WEBSERVICE_ERROR,
        ]

        for error in error_constants:
            assert len(error) == 2

    def test_all_error_codes_are_integers(self):
        """Test all error codes are integers."""
        from lys.core.consts import errors

        error_constants = [
            errors.NOT_UUID_ERROR,
            errors.PERMISSION_DENIED_ERROR,
            errors.NOT_FOUND_ERROR,
            errors.UNKNOWN_WEBSERVICE_ERROR,
        ]

        for error in error_constants:
            assert isinstance(error[0], int)

    def test_all_error_messages_are_strings(self):
        """Test all error messages are strings."""
        from lys.core.consts import errors

        error_constants = [
            errors.NOT_UUID_ERROR,
            errors.PERMISSION_DENIED_ERROR,
            errors.NOT_FOUND_ERROR,
            errors.UNKNOWN_WEBSERVICE_ERROR,
        ]

        for error in error_constants:
            assert isinstance(error[1], str)

    def test_all_error_messages_are_uppercase(self):
        """Test all error messages are uppercase."""
        from lys.core.consts import errors

        error_constants = [
            errors.NOT_UUID_ERROR,
            errors.PERMISSION_DENIED_ERROR,
            errors.NOT_FOUND_ERROR,
            errors.UNKNOWN_WEBSERVICE_ERROR,
        ]

        for error in error_constants:
            assert error[1] == error[1].upper()
