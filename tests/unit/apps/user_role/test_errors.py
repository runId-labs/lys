"""
Unit tests for user_role error codes.

Tests that all error codes are properly defined with correct HTTP status codes.
"""

import pytest


class TestForbiddenErrors:
    """Tests for 403 Forbidden errors."""

    def test_unauthorized_role_assignment(self):
        """Test UNAUTHORIZED_ROLE_ASSIGNMENT is defined with 403 status."""
        from lys.apps.user_role.errors import UNAUTHORIZED_ROLE_ASSIGNMENT

        assert UNAUTHORIZED_ROLE_ASSIGNMENT == (403, "UNAUTHORIZED_ROLE_ASSIGNMENT")

    def test_cannot_update_super_user_roles(self):
        """Test CANNOT_UPDATE_SUPER_USER_ROLES is defined with 403 status."""
        from lys.apps.user_role.errors import CANNOT_UPDATE_SUPER_USER_ROLES

        assert CANNOT_UPDATE_SUPER_USER_ROLES == (403, "CANNOT_UPDATE_SUPER_USER_ROLES")


class TestErrorTupleStructure:
    """Tests for error tuple structure consistency."""

    def test_all_errors_are_tuples(self):
        """Test that all errors are tuples with (status_code, error_name)."""
        from lys.apps.user_role import errors

        error_names = [
            "UNAUTHORIZED_ROLE_ASSIGNMENT",
            "CANNOT_UPDATE_SUPER_USER_ROLES",
        ]

        for name in error_names:
            error = getattr(errors, name)
            assert isinstance(error, tuple), f"{name} should be a tuple"
            assert len(error) == 2, f"{name} should have 2 elements"
            assert isinstance(error[0], int), f"{name} status code should be int"
            assert isinstance(error[1], str), f"{name} error name should be str"

    def test_error_codes_are_valid_http_status(self):
        """Test that all error codes are valid HTTP status codes."""
        from lys.apps.user_role import errors

        error_names = [
            "UNAUTHORIZED_ROLE_ASSIGNMENT",
            "CANNOT_UPDATE_SUPER_USER_ROLES",
        ]

        for name in error_names:
            error = getattr(errors, name)
            # 403 is a valid HTTP status code
            assert error[0] == 403, f"{name} should have 403 status code"

    def test_error_names_match_variable_names(self):
        """Test that error code strings match variable names."""
        from lys.apps.user_role.errors import (
            UNAUTHORIZED_ROLE_ASSIGNMENT,
            CANNOT_UPDATE_SUPER_USER_ROLES,
        )

        assert UNAUTHORIZED_ROLE_ASSIGNMENT[1] == "UNAUTHORIZED_ROLE_ASSIGNMENT"
        assert CANNOT_UPDATE_SUPER_USER_ROLES[1] == "CANNOT_UPDATE_SUPER_USER_ROLES"
