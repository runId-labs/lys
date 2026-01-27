"""
Unit tests for user_role constants.

Tests that all required constants are defined with expected values.
"""

import pytest


class TestRoleConstants:
    """Tests for role-related constants."""

    def test_user_admin_role(self):
        """Test USER_ADMIN_ROLE is defined."""
        from lys.apps.user_role.consts import USER_ADMIN_ROLE

        assert USER_ADMIN_ROLE == "USER_ADMIN_ROLE"

    def test_role_access_level(self):
        """Test ROLE_ACCESS_LEVEL is defined."""
        from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL

        assert ROLE_ACCESS_LEVEL == "ROLE"


class TestConstantsConsistency:
    """Tests for constants consistency."""

    def test_all_constants_are_strings(self):
        """Test that all constants are strings."""
        from lys.apps.user_role.consts import USER_ADMIN_ROLE, ROLE_ACCESS_LEVEL

        assert isinstance(USER_ADMIN_ROLE, str)
        assert isinstance(ROLE_ACCESS_LEVEL, str)

    def test_constants_are_uppercase(self):
        """Test that constant values follow naming conventions."""
        from lys.apps.user_role.consts import USER_ADMIN_ROLE, ROLE_ACCESS_LEVEL

        # USER_ADMIN_ROLE should be uppercase with underscores
        assert USER_ADMIN_ROLE == USER_ADMIN_ROLE.upper()
        # ROLE_ACCESS_LEVEL should be uppercase
        assert ROLE_ACCESS_LEVEL == ROLE_ACCESS_LEVEL.upper()
