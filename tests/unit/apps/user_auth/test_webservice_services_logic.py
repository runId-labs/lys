"""
Unit tests for user_auth webservice services logic.

Tests that AuthWebserviceService.accessible_webservices references
the enabled column for filtering disabled webservices.
Note: Methods using SQLAlchemy select() are tested at integration level.
"""

import inspect
import textwrap

from lys.apps.user_auth.modules.webservice.services import AuthWebserviceService


class TestAccessibleWebservicesEnabledFilter:
    """Tests that accessible_webservices filters on the enabled column."""

    def test_accessible_webservices_references_enabled_filter(self):
        """Test that the source code of accessible_webservices filters on enabled."""
        source = inspect.getsource(AuthWebserviceService.accessible_webservices)
        assert "enabled" in source, "accessible_webservices must filter on the enabled column"

    def test_accessible_webservices_uses_is_true(self):
        """Test that the enabled filter uses .is_(True) for SQLAlchemy idiom."""
        source = inspect.getsource(AuthWebserviceService.accessible_webservices)
        assert ".is_(True)" in source, "enabled filter should use .is_(True) instead of == True"