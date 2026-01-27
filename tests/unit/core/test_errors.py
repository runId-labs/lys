"""
Unit tests for core errors module.

Tests LysError exception class.
"""

import pytest
from fastapi import HTTPException


class TestLysError:
    """Tests for LysError exception class."""

    def test_class_exists(self):
        """Test LysError class exists."""
        from lys.core.errors import LysError
        assert LysError is not None

    def test_inherits_from_http_exception(self):
        """Test LysError inherits from HTTPException."""
        from lys.core.errors import LysError
        assert issubclass(LysError, HTTPException)

    def test_can_create_instance(self):
        """Test LysError can be instantiated."""
        from lys.core.errors import LysError
        error = LysError((400, "BAD_REQUEST"), "Test debug message")
        assert error is not None

    def test_status_code_from_tuple(self):
        """Test status_code is extracted from message tuple."""
        from lys.core.errors import LysError
        error = LysError((403, "FORBIDDEN"), "Debug message")
        assert error.status_code == 403

    def test_detail_from_tuple(self):
        """Test detail is extracted from message tuple."""
        from lys.core.errors import LysError
        error = LysError((404, "NOT_FOUND"), "Debug message")
        assert error.detail == "NOT_FOUND"

    def test_debug_message_stored(self):
        """Test debug_message is stored."""
        from lys.core.errors import LysError
        error = LysError((500, "INTERNAL"), "This is a debug message")
        assert error.debug_message == "This is a debug message"

    def test_extensions_default_to_empty_dict(self):
        """Test extensions default to empty dict with status_code."""
        from lys.core.errors import LysError
        error = LysError((400, "BAD_REQUEST"), "Debug")
        assert isinstance(error.extensions, dict)
        assert error.extensions["status_code"] == 400

    def test_extensions_with_custom_values(self):
        """Test extensions can have custom values."""
        from lys.core.errors import LysError
        custom_ext = {"field": "username", "value": "invalid"}
        error = LysError((400, "VALIDATION"), "Debug", extensions=custom_ext)
        assert error.extensions["field"] == "username"
        assert error.extensions["value"] == "invalid"
        assert error.extensions["status_code"] == 400

    def test_str_returns_detail(self):
        """Test __str__ returns only the error message."""
        from lys.core.errors import LysError
        error = LysError((400, "MY_ERROR_CODE"), "Debug message")
        assert str(error) == "MY_ERROR_CODE"

    def test_can_be_raised(self):
        """Test LysError can be raised."""
        from lys.core.errors import LysError
        with pytest.raises(LysError) as exc_info:
            raise LysError((400, "RAISED"), "This was raised")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "RAISED"

    def test_can_be_caught_as_http_exception(self):
        """Test LysError can be caught as HTTPException."""
        from lys.core.errors import LysError
        with pytest.raises(HTTPException):
            raise LysError((500, "SERVER_ERROR"), "Debug")


class TestLysErrorWithRealConstants:
    """Tests for LysError with real error constants."""

    def test_with_not_uuid_error(self):
        """Test LysError with NOT_UUID_ERROR constant."""
        from lys.core.errors import LysError
        from lys.core.consts.errors import NOT_UUID_ERROR
        error = LysError(NOT_UUID_ERROR, "Expected UUID format")
        assert error.status_code == 400
        assert error.detail == "NOT_UUID"

    def test_with_permission_denied_error(self):
        """Test LysError with PERMISSION_DENIED_ERROR constant."""
        from lys.core.errors import LysError
        from lys.core.consts.errors import PERMISSION_DENIED_ERROR
        error = LysError(PERMISSION_DENIED_ERROR, "User not authorized")
        assert error.status_code == 403
        assert error.detail == "PERMISSION_DENIED"

    def test_with_not_found_error(self):
        """Test LysError with NOT_FOUND_ERROR constant."""
        from lys.core.errors import LysError
        from lys.core.consts.errors import NOT_FOUND_ERROR
        error = LysError(NOT_FOUND_ERROR, "Resource not found")
        assert error.status_code == 404
        assert error.detail == "NOT_FOUND"

    def test_with_unknown_webservice_error(self):
        """Test LysError with UNKNOWN_WEBSERVICE_ERROR constant."""
        from lys.core.errors import LysError
        from lys.core.consts.errors import UNKNOWN_WEBSERVICE_ERROR
        error = LysError(UNKNOWN_WEBSERVICE_ERROR, "Webservice not registered")
        assert error.status_code == 404
        assert error.detail == "UNKNOWN_WEBSERVICE"
