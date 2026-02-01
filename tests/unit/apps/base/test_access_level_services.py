"""
Unit tests for base access_level module services.

Tests service structure.
"""

import pytest


class TestAccessLevelService:
    """Tests for AccessLevelService."""

    def test_service_exists(self):
        """Test AccessLevelService class exists."""
        from lys.apps.base.modules.access_level.services import AccessLevelService
        assert AccessLevelService is not None

    def test_service_inherits_from_entity_service(self):
        """Test AccessLevelService inherits from EntityService."""
        from lys.apps.base.modules.access_level.services import AccessLevelService
        from lys.core.services import EntityService
        assert issubclass(AccessLevelService, EntityService)

    def test_service_is_generic_over_access_level(self):
        """Test AccessLevelService is typed for AccessLevel entity."""
        from lys.apps.base.modules.access_level.services import AccessLevelService
        from lys.apps.base.modules.access_level.entities import AccessLevel
        # The service should have entity_class set to AccessLevel
        assert AccessLevelService.entity_class == AccessLevel
