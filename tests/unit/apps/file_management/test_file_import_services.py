"""
Unit tests for file_management file_import module services.

Tests service structure and method signatures.
"""

import pytest
import inspect


class TestFileImportTypeService:
    """Tests for FileImportTypeService."""

    def test_service_exists(self):
        """Test FileImportTypeService class exists."""
        from lys.apps.file_management.modules.file_import.services import FileImportTypeService
        assert FileImportTypeService is not None

    def test_service_inherits_from_entity_service(self):
        """Test FileImportTypeService inherits from EntityService."""
        from lys.apps.file_management.modules.file_import.services import FileImportTypeService
        from lys.core.services import EntityService
        assert issubclass(FileImportTypeService, EntityService)


class TestFileImportStatusService:
    """Tests for FileImportStatusService."""

    def test_service_exists(self):
        """Test FileImportStatusService class exists."""
        from lys.apps.file_management.modules.file_import.services import FileImportStatusService
        assert FileImportStatusService is not None

    def test_service_inherits_from_entity_service(self):
        """Test FileImportStatusService inherits from EntityService."""
        from lys.apps.file_management.modules.file_import.services import FileImportStatusService
        from lys.core.services import EntityService
        assert issubclass(FileImportStatusService, EntityService)


class TestFileImportService:
    """Tests for FileImportService."""

    def test_service_exists(self):
        """Test FileImportService class exists."""
        from lys.apps.file_management.modules.file_import.services import FileImportService
        assert FileImportService is not None

    def test_service_inherits_from_entity_service(self):
        """Test FileImportService inherits from EntityService."""
        from lys.apps.file_management.modules.file_import.services import FileImportService
        from lys.core.services import EntityService
        assert issubclass(FileImportService, EntityService)

    def test_create_import_method_exists(self):
        """Test create_import method exists."""
        from lys.apps.file_management.modules.file_import.services import FileImportService
        assert hasattr(FileImportService, "create_import")

    def test_create_import_is_async(self):
        """Test create_import is async."""
        from lys.apps.file_management.modules.file_import.services import FileImportService
        assert inspect.iscoroutinefunction(FileImportService.create_import)

    def test_create_import_signature(self):
        """Test create_import method signature."""
        from lys.apps.file_management.modules.file_import.services import FileImportService

        sig = inspect.signature(FileImportService.create_import)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "stored_file_id" in params
        assert "type_id" in params

    def test_update_progress_method_exists(self):
        """Test update_progress method exists."""
        from lys.apps.file_management.modules.file_import.services import FileImportService
        assert hasattr(FileImportService, "update_progress")

    def test_update_progress_signature(self):
        """Test update_progress method signature."""
        from lys.apps.file_management.modules.file_import.services import FileImportService

        sig = inspect.signature(FileImportService.update_progress)
        params = list(sig.parameters.keys())
        assert "file_import" in params
        assert "status_id" in params


class TestAbstractImportService:
    """Tests for AbstractImportService."""

    def test_class_exists(self):
        """Test AbstractImportService class exists."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert AbstractImportService is not None

    def test_class_is_abstract(self):
        """Test AbstractImportService is abstract."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        import abc
        assert issubclass(AbstractImportService, abc.ABC)

    def test_has_import_type_attribute(self):
        """Test AbstractImportService has import_type attribute."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "import_type")

    def test_has_unique_column_attribute(self):
        """Test AbstractImportService has unique_column attribute."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "unique_column")

    def test_has_delete_file_after_import_attribute(self):
        """Test AbstractImportService has delete_file_after_import attribute."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "delete_file_after_import")
        assert AbstractImportService.delete_file_after_import is True

    def test_has_reader_mapping(self):
        """Test AbstractImportService has READER_MAPPING."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        from lys.apps.file_management.modules.file_import.consts import (
            CSV_MIME_TYPE,
            XLS_MIME_TYPE,
            XLSX_MIME_TYPE,
        )

        assert hasattr(AbstractImportService, "READER_MAPPING")
        assert CSV_MIME_TYPE in AbstractImportService.READER_MAPPING
        assert XLS_MIME_TYPE in AbstractImportService.READER_MAPPING
        assert XLSX_MIME_TYPE in AbstractImportService.READER_MAPPING

    def test_get_column_mapping_is_abstract(self):
        """Test get_column_mapping is abstract method."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "get_column_mapping")

    def test_init_entity_is_abstract(self):
        """Test init_entity is abstract method."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "init_entity")

    def test_has_parse_file_method(self):
        """Test AbstractImportService has parse_file method."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "parse_file")

    def test_has_prepare_import_method(self):
        """Test AbstractImportService has prepare_import method."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "prepare_import")

    def test_has_on_import_start_hook(self):
        """Test AbstractImportService has on_import_start hook."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "on_import_start")

    def test_has_on_import_end_hook(self):
        """Test AbstractImportService has on_import_end hook."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "on_import_end")

    def test_has_on_row_success_hook(self):
        """Test AbstractImportService has on_row_success hook."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "on_row_success")

    def test_has_on_row_error_hook(self):
        """Test AbstractImportService has on_row_error hook."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "on_row_error")

    def test_has_perform_import_method(self):
        """Test AbstractImportService has perform_import method."""
        from lys.apps.file_management.modules.file_import.services import AbstractImportService
        assert hasattr(AbstractImportService, "perform_import")
