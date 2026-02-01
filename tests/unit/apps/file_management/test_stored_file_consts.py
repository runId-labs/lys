"""
Unit tests for file_management stored_file module constants.

Tests constant definitions and values.
"""

import pytest


class TestFileStoragePluginConstants:
    """Tests for file storage plugin configuration constants."""

    def test_file_storage_plugin_key(self):
        """Test FILE_STORAGE_PLUGIN_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_PLUGIN_KEY
        assert FILE_STORAGE_PLUGIN_KEY == "file_storage"

    def test_file_storage_backend_key(self):
        """Test FILE_STORAGE_BACKEND_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_BACKEND_KEY
        assert FILE_STORAGE_BACKEND_KEY == "backend"

    def test_file_storage_bucket_key(self):
        """Test FILE_STORAGE_BUCKET_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_BUCKET_KEY
        assert FILE_STORAGE_BUCKET_KEY == "bucket"

    def test_file_storage_access_key_key(self):
        """Test FILE_STORAGE_ACCESS_KEY_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_ACCESS_KEY_KEY
        assert FILE_STORAGE_ACCESS_KEY_KEY == "access_key"

    def test_file_storage_secret_key_key(self):
        """Test FILE_STORAGE_SECRET_KEY_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_SECRET_KEY_KEY
        assert FILE_STORAGE_SECRET_KEY_KEY == "secret_key"

    def test_file_storage_region_key(self):
        """Test FILE_STORAGE_REGION_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_REGION_KEY
        assert FILE_STORAGE_REGION_KEY == "region"

    def test_file_storage_endpoint_url_key(self):
        """Test FILE_STORAGE_ENDPOINT_URL_KEY is defined."""
        from lys.apps.file_management.modules.stored_file.consts import FILE_STORAGE_ENDPOINT_URL_KEY
        assert FILE_STORAGE_ENDPOINT_URL_KEY == "endpoint_url"


class TestDefaultConstants:
    """Tests for default configuration constants."""

    def test_default_presigned_url_expires(self):
        """Test DEFAULT_PRESIGNED_URL_EXPIRES is defined."""
        from lys.apps.file_management.modules.stored_file.consts import DEFAULT_PRESIGNED_URL_EXPIRES
        assert DEFAULT_PRESIGNED_URL_EXPIRES == 300  # 5 minutes

    def test_default_presigned_url_expires_is_integer(self):
        """Test DEFAULT_PRESIGNED_URL_EXPIRES is an integer."""
        from lys.apps.file_management.modules.stored_file.consts import DEFAULT_PRESIGNED_URL_EXPIRES
        assert isinstance(DEFAULT_PRESIGNED_URL_EXPIRES, int)


class TestConstantsConsistency:
    """Tests for constants consistency."""

    def test_all_keys_are_lowercase(self):
        """Test all plugin config keys are lowercase."""
        from lys.apps.file_management.modules.stored_file import consts

        keys = [
            consts.FILE_STORAGE_BACKEND_KEY,
            consts.FILE_STORAGE_BUCKET_KEY,
            consts.FILE_STORAGE_ACCESS_KEY_KEY,
            consts.FILE_STORAGE_SECRET_KEY_KEY,
            consts.FILE_STORAGE_REGION_KEY,
            consts.FILE_STORAGE_ENDPOINT_URL_KEY,
        ]

        for key in keys:
            assert key == key.lower()
