"""
Unit tests for base webservice module entities.

Tests entity structure.
"""

import pytest


class TestWebserviceEntity:
    """Tests for Webservice entity."""

    def test_entity_exists(self):
        """Test Webservice entity exists."""
        from lys.apps.base.modules.webservice.entities import Webservice
        assert Webservice is not None

    def test_entity_inherits_from_abstract_webservice(self):
        """Test Webservice inherits from AbstractWebservice."""
        from lys.apps.base.modules.webservice.entities import Webservice
        from lys.core.abstracts.webservices import AbstractWebservice
        assert issubclass(Webservice, AbstractWebservice)

    def test_entity_has_is_licenced_column(self):
        """Test Webservice has is_licenced column."""
        from lys.apps.base.modules.webservice.entities import Webservice
        assert "is_licenced" in Webservice.__annotations__

    def test_entity_has_app_name_column(self):
        """Test Webservice has app_name column."""
        from lys.apps.base.modules.webservice.entities import Webservice
        assert "app_name" in Webservice.__annotations__

    def test_entity_has_operation_type_column(self):
        """Test Webservice has operation_type column."""
        from lys.apps.base.modules.webservice.entities import Webservice
        assert "operation_type" in Webservice.__annotations__

    def test_entity_has_ai_tool_column(self):
        """Test Webservice has ai_tool column."""
        from lys.apps.base.modules.webservice.entities import Webservice
        assert "ai_tool" in Webservice.__annotations__

    def test_entity_has_is_public_property(self):
        """Test Webservice has is_public property."""
        from lys.apps.base.modules.webservice.entities import Webservice
        assert hasattr(Webservice, "is_public")

    def test_entity_has_access_levels_relationship(self):
        """Test Webservice has access_levels relationship."""
        from lys.apps.base.modules.webservice.entities import Webservice
        from tests.mocks.utils import has_relationship
        assert has_relationship(Webservice, "access_levels")


class TestWebserviceAccessLevelTable:
    """Tests for webservice_access_level association table."""

    def test_table_exists(self):
        """Test webservice_access_level table exists."""
        from lys.apps.base.modules.webservice.entities import webservice_access_level
        assert webservice_access_level is not None

    def test_table_name(self):
        """Test table has correct name."""
        from lys.apps.base.modules.webservice.entities import webservice_access_level
        assert webservice_access_level.name == "webservice_access_level"

    def test_table_has_webservice_id_column(self):
        """Test table has webservice_id column."""
        from lys.apps.base.modules.webservice.entities import webservice_access_level
        column_names = [col.name for col in webservice_access_level.columns]
        assert "webservice_id" in column_names

    def test_table_has_access_level_id_column(self):
        """Test table has access_level_id column."""
        from lys.apps.base.modules.webservice.entities import webservice_access_level
        column_names = [col.name for col in webservice_access_level.columns]
        assert "access_level_id" in column_names

    def test_table_has_created_at_column(self):
        """Test table has created_at column for audit trail."""
        from lys.apps.base.modules.webservice.entities import webservice_access_level
        column_names = [col.name for col in webservice_access_level.columns]
        assert "created_at" in column_names
