"""
Unit tests for core consts tablenames module.

Tests database table name constants.
"""

import pytest


class TestTablenameConstants:
    """Tests for tablename constants."""

    def test_access_level_tablename_exists(self):
        """Test ACCESS_LEVEL_TABLENAME is defined."""
        from lys.core.consts.tablenames import ACCESS_LEVEL_TABLENAME
        assert ACCESS_LEVEL_TABLENAME is not None

    def test_access_level_tablename_value(self):
        """Test ACCESS_LEVEL_TABLENAME has correct value."""
        from lys.core.consts.tablenames import ACCESS_LEVEL_TABLENAME
        assert ACCESS_LEVEL_TABLENAME == "access_level"

    def test_log_tablename_exists(self):
        """Test LOG_TABLENAME is defined."""
        from lys.core.consts.tablenames import LOG_TABLENAME
        assert LOG_TABLENAME is not None

    def test_log_tablename_value(self):
        """Test LOG_TABLENAME has correct value."""
        from lys.core.consts.tablenames import LOG_TABLENAME
        assert LOG_TABLENAME == "log"

    def test_webservice_tablename_exists(self):
        """Test WEBSERVICE_TABLENAME is defined."""
        from lys.core.consts.tablenames import WEBSERVICE_TABLENAME
        assert WEBSERVICE_TABLENAME is not None

    def test_webservice_tablename_value(self):
        """Test WEBSERVICE_TABLENAME has correct value."""
        from lys.core.consts.tablenames import WEBSERVICE_TABLENAME
        assert WEBSERVICE_TABLENAME == "webservice"


class TestTablenameConsistency:
    """Tests for tablename constants consistency."""

    def test_all_tablenames_are_lowercase(self):
        """Test all tablenames are lowercase."""
        from lys.core.consts.tablenames import (
            ACCESS_LEVEL_TABLENAME,
            LOG_TABLENAME,
            WEBSERVICE_TABLENAME,
        )

        tablenames = [ACCESS_LEVEL_TABLENAME, LOG_TABLENAME, WEBSERVICE_TABLENAME]

        for tablename in tablenames:
            assert tablename == tablename.lower()

    def test_all_tablenames_are_strings(self):
        """Test all tablenames are strings."""
        from lys.core.consts.tablenames import (
            ACCESS_LEVEL_TABLENAME,
            LOG_TABLENAME,
            WEBSERVICE_TABLENAME,
        )

        tablenames = [ACCESS_LEVEL_TABLENAME, LOG_TABLENAME, WEBSERVICE_TABLENAME]

        for tablename in tablenames:
            assert isinstance(tablename, str)

    def test_all_tablenames_are_unique(self):
        """Test all tablenames are unique."""
        from lys.core.consts.tablenames import (
            ACCESS_LEVEL_TABLENAME,
            LOG_TABLENAME,
            WEBSERVICE_TABLENAME,
        )

        tablenames = [ACCESS_LEVEL_TABLENAME, LOG_TABLENAME, WEBSERVICE_TABLENAME]
        assert len(tablenames) == len(set(tablenames))

    def test_tablenames_use_underscores(self):
        """Test tablenames use underscores not hyphens."""
        from lys.core.consts.tablenames import (
            ACCESS_LEVEL_TABLENAME,
            LOG_TABLENAME,
            WEBSERVICE_TABLENAME,
        )

        tablenames = [ACCESS_LEVEL_TABLENAME, LOG_TABLENAME, WEBSERVICE_TABLENAME]

        for tablename in tablenames:
            assert "-" not in tablename
