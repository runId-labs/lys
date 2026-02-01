"""
Unit tests for base log module entities.

Tests entity structure.
"""

import pytest


class TestLogEntity:
    """Tests for Log entity."""

    def test_entity_exists(self):
        """Test Log entity exists."""
        from lys.apps.base.modules.log.entities import Log
        assert Log is not None

    def test_entity_inherits_from_entity(self):
        """Test Log inherits from Entity."""
        from lys.apps.base.modules.log.entities import Log
        from lys.core.entities import Entity
        assert issubclass(Log, Entity)

    def test_entity_has_tablename(self):
        """Test Log has correct __tablename__."""
        from lys.apps.base.modules.log.entities import Log
        from lys.core.consts.tablenames import LOG_TABLENAME
        assert Log.__tablename__ == LOG_TABLENAME

    def test_entity_has_message_column(self):
        """Test Log has message column."""
        from lys.apps.base.modules.log.entities import Log
        assert hasattr(Log, "message")

    def test_entity_has_file_name_column(self):
        """Test Log has file_name column."""
        from lys.apps.base.modules.log.entities import Log
        assert "file_name" in Log.__annotations__

    def test_entity_has_line_column(self):
        """Test Log has line column."""
        from lys.apps.base.modules.log.entities import Log
        assert "line" in Log.__annotations__

    def test_entity_has_traceback_column(self):
        """Test Log has traceback column."""
        from lys.apps.base.modules.log.entities import Log
        assert hasattr(Log, "traceback")

    def test_entity_has_context_column(self):
        """Test Log has context column."""
        from lys.apps.base.modules.log.entities import Log
        assert hasattr(Log, "context")

    def test_entity_has_accessing_users_method(self):
        """Test Log has accessing_users method."""
        from lys.apps.base.modules.log.entities import Log
        assert hasattr(Log, "accessing_users")
        assert callable(Log.accessing_users)

    def test_entity_has_accessing_organizations_method(self):
        """Test Log has accessing_organizations method."""
        from lys.apps.base.modules.log.entities import Log
        assert hasattr(Log, "accessing_organizations")
        assert callable(Log.accessing_organizations)
