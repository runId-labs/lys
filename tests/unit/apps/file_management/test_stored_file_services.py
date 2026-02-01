"""
Unit tests for file_management stored_file module services.

Tests service structure and method signatures.
"""

import pytest
import inspect

# Skip all tests if aioboto3 is not installed
pytest.importorskip("aioboto3", reason="aioboto3 not installed")


class TestStoredFileTypeService:
    """Tests for StoredFileTypeService."""

    def test_service_exists(self):
        """Test StoredFileTypeService class exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileTypeService
        assert StoredFileTypeService is not None

    def test_service_inherits_from_entity_service(self):
        """Test StoredFileTypeService inherits from EntityService."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileTypeService
        from lys.core.services import EntityService
        assert issubclass(StoredFileTypeService, EntityService)


class TestStoredFileService:
    """Tests for StoredFileService."""

    def test_service_exists(self):
        """Test StoredFileService class exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert StoredFileService is not None

    def test_service_inherits_from_entity_service(self):
        """Test StoredFileService inherits from EntityService."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        from lys.core.services import EntityService
        assert issubclass(StoredFileService, EntityService)

    def test_has_storage_backend_attribute(self):
        """Test StoredFileService has _storage_backend class attribute."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "_storage_backend")

    def test_get_storage_backend_method_exists(self):
        """Test get_storage_backend method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "get_storage_backend")

    def test_generate_object_key_method_exists(self):
        """Test generate_object_key method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "generate_object_key")

    def test_generate_object_key_signature(self):
        """Test generate_object_key method signature."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService

        sig = inspect.signature(StoredFileService.generate_object_key)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "type_id" in params
        assert "original_name" in params

    def test_upload_method_exists(self):
        """Test upload method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "upload")

    def test_upload_is_async(self):
        """Test upload is async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert inspect.iscoroutinefunction(StoredFileService.upload)

    def test_download_method_exists(self):
        """Test download method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "download")

    def test_download_is_async(self):
        """Test download is async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert inspect.iscoroutinefunction(StoredFileService.download)

    def test_delete_file_method_exists(self):
        """Test delete_file method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "delete_file")

    def test_delete_file_is_async(self):
        """Test delete_file is async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert inspect.iscoroutinefunction(StoredFileService.delete_file)

    def test_get_presigned_url_method_exists(self):
        """Test get_presigned_url method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "get_presigned_url")

    def test_get_presigned_url_is_async(self):
        """Test get_presigned_url is async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert inspect.iscoroutinefunction(StoredFileService.get_presigned_url)

    def test_generate_presigned_upload_url_method_exists(self):
        """Test generate_presigned_upload_url method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "generate_presigned_upload_url")

    def test_generate_presigned_upload_url_is_async(self):
        """Test generate_presigned_upload_url is async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert inspect.iscoroutinefunction(StoredFileService.generate_presigned_upload_url)

    def test_create_from_uploaded_method_exists(self):
        """Test create_from_uploaded method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "create_from_uploaded")

    def test_create_from_uploaded_is_async(self):
        """Test create_from_uploaded is async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert inspect.iscoroutinefunction(StoredFileService.create_from_uploaded)


class TestStoredFileServiceSyncMethods:
    """Tests for StoredFileService sync methods (for Celery workers)."""

    def test_upload_sync_method_exists(self):
        """Test upload_sync method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "upload_sync")

    def test_upload_sync_is_not_async(self):
        """Test upload_sync is not async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert not inspect.iscoroutinefunction(StoredFileService.upload_sync)

    def test_download_sync_method_exists(self):
        """Test download_sync method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "download_sync")

    def test_download_sync_is_not_async(self):
        """Test download_sync is not async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert not inspect.iscoroutinefunction(StoredFileService.download_sync)

    def test_delete_file_sync_method_exists(self):
        """Test delete_file_sync method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "delete_file_sync")

    def test_delete_file_sync_is_not_async(self):
        """Test delete_file_sync is not async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert not inspect.iscoroutinefunction(StoredFileService.delete_file_sync)

    def test_get_presigned_url_sync_method_exists(self):
        """Test get_presigned_url_sync method exists."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert hasattr(StoredFileService, "get_presigned_url_sync")

    def test_get_presigned_url_sync_is_not_async(self):
        """Test get_presigned_url_sync is not async."""
        from lys.apps.file_management.modules.stored_file.services import StoredFileService
        assert not inspect.iscoroutinefunction(StoredFileService.get_presigned_url_sync)
