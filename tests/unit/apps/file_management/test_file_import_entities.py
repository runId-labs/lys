"""
Unit tests for file_management file_import module entities.

Tests entity structure.
"""

import pytest


class TestFileImportTypeEntity:
    """Tests for FileImportType entity."""

    def test_entity_exists(self):
        """Test FileImportType entity exists."""
        from lys.apps.file_management.modules.file_import.entities import FileImportType
        assert FileImportType is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test FileImportType inherits from ParametricEntity."""
        from lys.apps.file_management.modules.file_import.entities import FileImportType
        from lys.core.entities import ParametricEntity
        assert issubclass(FileImportType, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test FileImportType has correct __tablename__."""
        from lys.apps.file_management.modules.file_import.entities import FileImportType
        assert FileImportType.__tablename__ == "file_import_type"


class TestFileImportStatusEntity:
    """Tests for FileImportStatus entity."""

    def test_entity_exists(self):
        """Test FileImportStatus entity exists."""
        from lys.apps.file_management.modules.file_import.entities import FileImportStatus
        assert FileImportStatus is not None

    def test_entity_inherits_from_parametric_entity(self):
        """Test FileImportStatus inherits from ParametricEntity."""
        from lys.apps.file_management.modules.file_import.entities import FileImportStatus
        from lys.core.entities import ParametricEntity
        assert issubclass(FileImportStatus, ParametricEntity)

    def test_entity_has_tablename(self):
        """Test FileImportStatus has correct __tablename__."""
        from lys.apps.file_management.modules.file_import.entities import FileImportStatus
        assert FileImportStatus.__tablename__ == "file_import_status"


class TestFileImportEntity:
    """Tests for FileImport entity."""

    def test_entity_exists(self):
        """Test FileImport entity exists."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert FileImport is not None

    def test_entity_inherits_from_entity(self):
        """Test FileImport inherits from Entity."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        from lys.core.entities import Entity
        assert issubclass(FileImport, Entity)

    def test_entity_has_tablename(self):
        """Test FileImport has correct __tablename__."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert FileImport.__tablename__ == "file_import"

    def test_entity_has_client_id_column(self):
        """Test FileImport has client_id column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "client_id" in FileImport.__annotations__

    def test_entity_has_stored_file_id_column(self):
        """Test FileImport has stored_file_id column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "stored_file_id" in FileImport.__annotations__

    def test_entity_has_type_id_column(self):
        """Test FileImport has type_id column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "type_id" in FileImport.__annotations__

    def test_entity_has_status_id_column(self):
        """Test FileImport has status_id column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "status_id" in FileImport.__annotations__

    def test_entity_has_total_rows_column(self):
        """Test FileImport has total_rows column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "total_rows" in FileImport.__annotations__

    def test_entity_has_processed_rows_column(self):
        """Test FileImport has processed_rows column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "processed_rows" in FileImport.__annotations__

    def test_entity_has_success_rows_column(self):
        """Test FileImport has success_rows column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "success_rows" in FileImport.__annotations__

    def test_entity_has_error_rows_column(self):
        """Test FileImport has error_rows column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "error_rows" in FileImport.__annotations__

    def test_entity_has_errors_column(self):
        """Test FileImport has errors column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "errors" in FileImport.__annotations__

    def test_entity_has_config_column(self):
        """Test FileImport has config column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "config" in FileImport.__annotations__

    def test_entity_has_extra_data_column(self):
        """Test FileImport has extra_data column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "extra_data" in FileImport.__annotations__

    def test_entity_has_started_at_column(self):
        """Test FileImport has started_at column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "started_at" in FileImport.__annotations__

    def test_entity_has_completed_at_column(self):
        """Test FileImport has completed_at column."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert "completed_at" in FileImport.__annotations__

    def test_entity_has_accessing_users_method(self):
        """Test FileImport has accessing_users method."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert hasattr(FileImport, "accessing_users")
        assert callable(FileImport.accessing_users)

    def test_entity_has_accessing_organizations_method(self):
        """Test FileImport has accessing_organizations method."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert hasattr(FileImport, "accessing_organizations")
        assert callable(FileImport.accessing_organizations)

    def test_entity_has_organization_accessing_filters_classmethod(self):
        """Test FileImport has organization_accessing_filters classmethod."""
        from lys.apps.file_management.modules.file_import.entities import FileImport
        assert hasattr(FileImport, "organization_accessing_filters")
