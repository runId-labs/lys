"""
Unit tests for core consts webservices module.

Tests webservice and access level constants.
"""

import pytest


class TestWebservicePublicTypeConstants:
    """Tests for webservice public type constants."""

    def test_no_limitation_public_type_exists(self):
        """Test NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE is defined."""
        from lys.core.consts.webservices import NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE
        assert NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE is not None

    def test_no_limitation_public_type_value(self):
        """Test NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE has correct value."""
        from lys.core.consts.webservices import NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE
        assert NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE == "NO_LIMITATION"

    def test_disconnected_public_type_exists(self):
        """Test DISCONNECTED_WEBSERVICE_PUBLIC_TYPE is defined."""
        from lys.core.consts.webservices import DISCONNECTED_WEBSERVICE_PUBLIC_TYPE
        assert DISCONNECTED_WEBSERVICE_PUBLIC_TYPE is not None

    def test_disconnected_public_type_value(self):
        """Test DISCONNECTED_WEBSERVICE_PUBLIC_TYPE has correct value."""
        from lys.core.consts.webservices import DISCONNECTED_WEBSERVICE_PUBLIC_TYPE
        assert DISCONNECTED_WEBSERVICE_PUBLIC_TYPE == "DISCONNECTED"


class TestAccessLevelConstants:
    """Tests for access level constants."""

    def test_connected_access_level_exists(self):
        """Test CONNECTED_ACCESS_LEVEL is defined."""
        from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
        assert CONNECTED_ACCESS_LEVEL is not None

    def test_connected_access_level_value(self):
        """Test CONNECTED_ACCESS_LEVEL has correct value."""
        from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
        assert CONNECTED_ACCESS_LEVEL == "CONNECTED"

    def test_owner_access_level_exists(self):
        """Test OWNER_ACCESS_LEVEL is defined."""
        from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
        assert OWNER_ACCESS_LEVEL is not None

    def test_owner_access_level_value(self):
        """Test OWNER_ACCESS_LEVEL has correct value."""
        from lys.core.consts.webservices import OWNER_ACCESS_LEVEL
        assert OWNER_ACCESS_LEVEL == "OWNER"

    def test_internal_service_access_level_exists(self):
        """Test INTERNAL_SERVICE_ACCESS_LEVEL is defined."""
        from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL
        assert INTERNAL_SERVICE_ACCESS_LEVEL is not None

    def test_internal_service_access_level_value(self):
        """Test INTERNAL_SERVICE_ACCESS_LEVEL has correct value."""
        from lys.core.consts.webservices import INTERNAL_SERVICE_ACCESS_LEVEL
        assert INTERNAL_SERVICE_ACCESS_LEVEL == "INTERNAL_SERVICE"


class TestWebserviceConstantsConsistency:
    """Tests for webservice constants consistency."""

    def test_all_public_types_are_uppercase(self):
        """Test all public type constants are uppercase."""
        from lys.core.consts.webservices import (
            NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
            DISCONNECTED_WEBSERVICE_PUBLIC_TYPE,
        )

        types = [NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE, DISCONNECTED_WEBSERVICE_PUBLIC_TYPE]

        for type_value in types:
            assert type_value == type_value.upper()

    def test_all_access_levels_are_uppercase(self):
        """Test all access level constants are uppercase."""
        from lys.core.consts.webservices import (
            CONNECTED_ACCESS_LEVEL,
            OWNER_ACCESS_LEVEL,
            INTERNAL_SERVICE_ACCESS_LEVEL,
        )

        levels = [CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL, INTERNAL_SERVICE_ACCESS_LEVEL]

        for level in levels:
            assert level == level.upper()

    def test_all_constants_are_strings(self):
        """Test all constants are strings."""
        from lys.core.consts.webservices import (
            NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
            DISCONNECTED_WEBSERVICE_PUBLIC_TYPE,
            CONNECTED_ACCESS_LEVEL,
            OWNER_ACCESS_LEVEL,
            INTERNAL_SERVICE_ACCESS_LEVEL,
        )

        constants = [
            NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
            DISCONNECTED_WEBSERVICE_PUBLIC_TYPE,
            CONNECTED_ACCESS_LEVEL,
            OWNER_ACCESS_LEVEL,
            INTERNAL_SERVICE_ACCESS_LEVEL,
        ]

        for constant in constants:
            assert isinstance(constant, str)

    def test_all_constants_use_underscores(self):
        """Test all constants use underscores not hyphens."""
        from lys.core.consts.webservices import (
            NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
            DISCONNECTED_WEBSERVICE_PUBLIC_TYPE,
            CONNECTED_ACCESS_LEVEL,
            OWNER_ACCESS_LEVEL,
            INTERNAL_SERVICE_ACCESS_LEVEL,
        )

        constants = [
            NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE,
            DISCONNECTED_WEBSERVICE_PUBLIC_TYPE,
            CONNECTED_ACCESS_LEVEL,
            OWNER_ACCESS_LEVEL,
            INTERNAL_SERVICE_ACCESS_LEVEL,
        ]

        for constant in constants:
            assert "-" not in constant
