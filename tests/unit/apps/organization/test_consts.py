"""
Unit tests for organization app constants.

Tests the constant values used throughout the organization module.
"""

import pytest


class TestOrganizationConstants:
    """Tests for organization constant values."""

    def test_organization_role_access_level(self):
        """Test ORGANIZATION_ROLE_ACCESS_LEVEL constant."""
        from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL

        assert ORGANIZATION_ROLE_ACCESS_LEVEL == "ORGANIZATION_ROLE"

    def test_client_admin_role(self):
        """Test CLIENT_ADMIN_ROLE constant."""
        from lys.apps.organization.consts import CLIENT_ADMIN_ROLE

        assert CLIENT_ADMIN_ROLE == "CLIENT_ADMIN_ROLE"

    def test_invalid_client_id_error(self):
        """Test INVALID_CLIENT_ID error tuple."""
        from lys.apps.organization.consts import INVALID_CLIENT_ID

        assert isinstance(INVALID_CLIENT_ID, tuple)
        assert len(INVALID_CLIENT_ID) == 2
        assert INVALID_CLIENT_ID[0] == 400
        assert INVALID_CLIENT_ID[1] == "INVALID_CLIENT_ID"


class TestConstantsConsistency:
    """Tests for constant consistency."""

    def test_all_constants_are_strings_or_tuples(self):
        """Test that all constants are strings or tuples."""
        from lys.apps.organization import consts

        for name in dir(consts):
            if not name.startswith("_"):
                value = getattr(consts, name)
                assert isinstance(value, (str, tuple)), f"{name} should be string or tuple"

    def test_access_level_is_uppercase(self):
        """Test that access level constants are uppercase."""
        from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL

        assert ORGANIZATION_ROLE_ACCESS_LEVEL.isupper()

    def test_role_constant_is_uppercase(self):
        """Test that role constant is uppercase."""
        from lys.apps.organization.consts import CLIENT_ADMIN_ROLE

        assert CLIENT_ADMIN_ROLE.isupper()
