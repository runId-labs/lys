"""
Unit tests for StoredFileService.generate_object_key() — pure logic.
"""
from unittest.mock import patch
from datetime import datetime, timezone

from lys.apps.file_management.modules.stored_file.services import StoredFileService


class TestGenerateObjectKey:
    """Tests for StoredFileService.generate_object_key()."""

    @patch("lys.apps.file_management.modules.stored_file.services.uuid.uuid4")
    @patch("lys.apps.file_management.modules.stored_file.services.datetime")
    def test_format(self, mock_datetime, mock_uuid):
        mock_datetime.now.return_value = datetime(2024, 3, 15, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_uuid.return_value = "aaaa-bbbb-cccc"
        key = StoredFileService.generate_object_key("client-1", "USER_IMPORT", "data.csv")
        assert key == "client-1/USER_IMPORT/2024/03/15/aaaa-bbbb-cccc.csv"

    @patch("lys.apps.file_management.modules.stored_file.services.uuid.uuid4")
    @patch("lys.apps.file_management.modules.stored_file.services.datetime")
    def test_no_extension(self, mock_datetime, mock_uuid):
        mock_datetime.now.return_value = datetime(2024, 1, 5, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_uuid.return_value = "1234"
        key = StoredFileService.generate_object_key("client-1", "TYPE", "readme")
        assert key == "client-1/TYPE/2024/01/05/1234"

    @patch("lys.apps.file_management.modules.stored_file.services.uuid.uuid4")
    @patch("lys.apps.file_management.modules.stored_file.services.datetime")
    def test_uppercase_extension_lowered(self, mock_datetime, mock_uuid):
        mock_datetime.now.return_value = datetime(2024, 6, 1, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_uuid.return_value = "uuid"
        key = StoredFileService.generate_object_key("c", "T", "Photo.JPG")
        assert key.endswith(".jpg")

    @patch("lys.apps.file_management.modules.stored_file.services.uuid.uuid4")
    @patch("lys.apps.file_management.modules.stored_file.services.datetime")
    def test_multiple_dots_uses_last_extension(self, mock_datetime, mock_uuid):
        mock_datetime.now.return_value = datetime(2024, 6, 1, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_uuid.return_value = "uuid"
        key = StoredFileService.generate_object_key("c", "T", "archive.tar.gz")
        assert key.endswith(".gz")

    @patch("lys.apps.file_management.modules.stored_file.services.uuid.uuid4")
    @patch("lys.apps.file_management.modules.stored_file.services.datetime")
    def test_month_day_zero_padded(self, mock_datetime, mock_uuid):
        mock_datetime.now.return_value = datetime(2024, 1, 5, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_uuid.return_value = "id"
        key = StoredFileService.generate_object_key("c", "T", "f.txt")
        assert "/01/05/" in key
