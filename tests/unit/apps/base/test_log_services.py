"""
Unit tests for base log module services.

Tests service structure.
"""

import pytest


class TestLogService:
    """Tests for LogService."""

    def test_service_exists(self):
        """Test LogService class exists."""
        from lys.apps.base.modules.log.services import LogService
        assert LogService is not None

    def test_service_inherits_from_entity_service(self):
        """Test LogService inherits from EntityService."""
        from lys.apps.base.modules.log.services import LogService
        from lys.core.services import EntityService
        assert issubclass(LogService, EntityService)

    def test_service_is_generic_over_log(self):
        """Test LogService is typed for Log entity."""
        from lys.apps.base.modules.log.services import LogService
        from lys.apps.base.modules.log.entities import Log
        assert LogService.entity_class == Log
