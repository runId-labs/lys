"""
Unit tests for core consts permissions module.

Tests permission key constants.
"""

import pytest


class TestPermissionKeyConstants:
    """Tests for permission key constants."""

    def test_role_access_key_exists(self):
        """Test ROLE_ACCESS_KEY is defined."""
        from lys.core.consts.permissions import ROLE_ACCESS_KEY
        assert ROLE_ACCESS_KEY is not None

    def test_role_access_key_value(self):
        """Test ROLE_ACCESS_KEY has correct value."""
        from lys.core.consts.permissions import ROLE_ACCESS_KEY
        assert ROLE_ACCESS_KEY == "role"

    def test_owner_access_key_exists(self):
        """Test OWNER_ACCESS_KEY is defined."""
        from lys.core.consts.permissions import OWNER_ACCESS_KEY
        assert OWNER_ACCESS_KEY is not None

    def test_owner_access_key_value(self):
        """Test OWNER_ACCESS_KEY has correct value."""
        from lys.core.consts.permissions import OWNER_ACCESS_KEY
        assert OWNER_ACCESS_KEY == "owner"

    def test_organization_role_access_key_exists(self):
        """Test ORGANIZATION_ROLE_ACCESS_KEY is defined."""
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY
        assert ORGANIZATION_ROLE_ACCESS_KEY is not None

    def test_organization_role_access_key_value(self):
        """Test ORGANIZATION_ROLE_ACCESS_KEY has correct value."""
        from lys.core.consts.permissions import ORGANIZATION_ROLE_ACCESS_KEY
        assert ORGANIZATION_ROLE_ACCESS_KEY == "organization_role"


class TestPermissionKeyConsistency:
    """Tests for permission key constants consistency."""

    def test_all_keys_are_lowercase(self):
        """Test all permission keys are lowercase."""
        from lys.core.consts.permissions import (
            ROLE_ACCESS_KEY,
            OWNER_ACCESS_KEY,
            ORGANIZATION_ROLE_ACCESS_KEY,
        )

        keys = [ROLE_ACCESS_KEY, OWNER_ACCESS_KEY, ORGANIZATION_ROLE_ACCESS_KEY]

        for key in keys:
            assert key == key.lower()

    def test_all_keys_are_strings(self):
        """Test all permission keys are strings."""
        from lys.core.consts.permissions import (
            ROLE_ACCESS_KEY,
            OWNER_ACCESS_KEY,
            ORGANIZATION_ROLE_ACCESS_KEY,
        )

        keys = [ROLE_ACCESS_KEY, OWNER_ACCESS_KEY, ORGANIZATION_ROLE_ACCESS_KEY]

        for key in keys:
            assert isinstance(key, str)

    def test_all_keys_are_unique(self):
        """Test all permission keys are unique."""
        from lys.core.consts.permissions import (
            ROLE_ACCESS_KEY,
            OWNER_ACCESS_KEY,
            ORGANIZATION_ROLE_ACCESS_KEY,
        )

        keys = [ROLE_ACCESS_KEY, OWNER_ACCESS_KEY, ORGANIZATION_ROLE_ACCESS_KEY]
        assert len(keys) == len(set(keys))
