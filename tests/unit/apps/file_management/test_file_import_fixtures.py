"""
Unit tests for file_management file_import module fixtures.

Tests fixtures configuration and data.
"""

import pytest


class TestFileImportStatusFixtures:
    """Tests for FileImportStatusFixtures."""

    def test_fixture_exists(self):
        """Test FileImportStatusFixtures class exists."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        assert FileImportStatusFixtures is not None

    def test_fixture_inherits_from_entity_fixtures(self):
        """Test FileImportStatusFixtures inherits from EntityFixtures."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(FileImportStatusFixtures, EntityFixtures)

    def test_fixture_has_model(self):
        """Test FileImportStatusFixtures has model attribute."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.core.models.fixtures import ParametricEntityFixturesModel
        assert FileImportStatusFixtures.model == ParametricEntityFixturesModel

    def test_fixture_has_data_list(self):
        """Test FileImportStatusFixtures has data_list attribute."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        assert hasattr(FileImportStatusFixtures, "data_list")
        assert isinstance(FileImportStatusFixtures.data_list, list)

    def test_data_list_contains_pending_status(self):
        """Test data_list contains PENDING status."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_PENDING

        ids = [item["id"] for item in FileImportStatusFixtures.data_list]
        assert FILE_IMPORT_STATUS_PENDING in ids

    def test_data_list_contains_processing_status(self):
        """Test data_list contains PROCESSING status."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_PROCESSING

        ids = [item["id"] for item in FileImportStatusFixtures.data_list]
        assert FILE_IMPORT_STATUS_PROCESSING in ids

    def test_data_list_contains_completed_status(self):
        """Test data_list contains COMPLETED status."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_COMPLETED

        ids = [item["id"] for item in FileImportStatusFixtures.data_list]
        assert FILE_IMPORT_STATUS_COMPLETED in ids

    def test_data_list_contains_failed_status(self):
        """Test data_list contains FAILED status."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_FAILED

        ids = [item["id"] for item in FileImportStatusFixtures.data_list]
        assert FILE_IMPORT_STATUS_FAILED in ids

    def test_data_list_contains_cancelled_status(self):
        """Test data_list contains CANCELLED status."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_CANCELLED

        ids = [item["id"] for item in FileImportStatusFixtures.data_list]
        assert FILE_IMPORT_STATUS_CANCELLED in ids

    def test_all_statuses_are_enabled(self):
        """Test all statuses are enabled."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures

        for item in FileImportStatusFixtures.data_list:
            assert item["attributes"]["enabled"] is True

    def test_data_list_has_five_statuses(self):
        """Test data_list has exactly five statuses."""
        from lys.apps.file_management.modules.file_import.fixtures import FileImportStatusFixtures
        assert len(FileImportStatusFixtures.data_list) == 5
