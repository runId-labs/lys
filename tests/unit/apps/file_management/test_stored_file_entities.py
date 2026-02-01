"""
Unit tests for file_management stored_file module entities.

Tests entity structure.
"""

import pytest


class TestStoredFileTypeEntity:
    """Tests for StoredFileType entity."""

    def test_entity_exists(self):
        """Test StoredFileType entity exists."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFileType
        assert StoredFileType is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test StoredFileType inherits from ParametricEntity."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFileType
        from lys.core.entities import ParametricEntity
        assert issubclass(StoredFileType, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test StoredFileType has correct __tablename__."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFileType
        assert StoredFileType.__tablename__ == "stored_file_type"


class TestStoredFileEntity:
    """Tests for StoredFile entity."""

    def test_entity_exists(self):
        """Test StoredFile entity exists."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert StoredFile is not None

    def test_entity_inherits_from_entity(self):
        """Test StoredFile inherits from Entity."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        from lys.core.entities import Entity
        assert issubclass(StoredFile, Entity)

    def test_entity_has_tablename(self):
        """Test StoredFile has correct __tablename__."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert StoredFile.__tablename__ == "stored_file"

    def test_entity_has_client_id_column(self):
        """Test StoredFile has client_id column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "client_id" in StoredFile.__annotations__

    def test_entity_has_original_name_column(self):
        """Test StoredFile has original_name column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "original_name" in StoredFile.__annotations__

    def test_entity_has_size_column(self):
        """Test StoredFile has size column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "size" in StoredFile.__annotations__

    def test_entity_has_mime_type_column(self):
        """Test StoredFile has mime_type column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "mime_type" in StoredFile.__annotations__

    def test_entity_has_type_id_column(self):
        """Test StoredFile has type_id column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "type_id" in StoredFile.__annotations__

    def test_entity_has_object_key_column(self):
        """Test StoredFile has object_key column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "object_key" in StoredFile.__annotations__

    def test_entity_has_extra_data_column(self):
        """Test StoredFile has extra_data column."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert "extra_data" in StoredFile.__annotations__

    def test_entity_has_path_property(self):
        """Test StoredFile has path property."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert hasattr(StoredFile, "path")

    def test_entity_has_accessing_users_method(self):
        """Test StoredFile has accessing_users method."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert hasattr(StoredFile, "accessing_users")
        assert callable(StoredFile.accessing_users)

    def test_entity_has_accessing_organizations_method(self):
        """Test StoredFile has accessing_organizations method."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert hasattr(StoredFile, "accessing_organizations")
        assert callable(StoredFile.accessing_organizations)

    def test_entity_has_organization_accessing_filters_classmethod(self):
        """Test StoredFile has organization_accessing_filters classmethod."""
        from lys.apps.file_management.modules.stored_file.entities import StoredFile
        assert hasattr(StoredFile, "organization_accessing_filters")
