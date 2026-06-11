"""
Unit tests for StoredFileService.generate_object_key() — pure logic.
"""
import hashlib
import io
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


class TestContentHash:
    """Tests for StoredFileService.content_hash() — SHA-256 of in-memory bytes only."""

    def test_bytes_returns_sha256_hex(self):
        data = b"hello world"
        assert StoredFileService.content_hash(data) == hashlib.sha256(data).hexdigest()

    def test_bytearray_is_hashed(self):
        assert StoredFileService.content_hash(bytearray(b"abc")) == hashlib.sha256(b"abc").hexdigest()

    def test_empty_bytes_is_hashed(self):
        assert StoredFileService.content_hash(b"") == hashlib.sha256(b"").hexdigest()

    def test_same_content_same_hash(self):
        assert StoredFileService.content_hash(b"x") == StoredFileService.content_hash(b"x")

    def test_different_content_different_hash(self):
        assert StoredFileService.content_hash(b"a") != StoredFileService.content_hash(b"b")

    def test_hash_is_64_hex_chars(self):
        digest = StoredFileService.content_hash(b"anything")
        assert len(digest) == 64
        int(digest, 16)  # parses as hexadecimal

    def test_stream_returns_none(self):
        assert StoredFileService.content_hash(io.BytesIO(b"data")) is None

    def test_stream_is_not_consumed(self):
        stream = io.BytesIO(b"payload")
        StoredFileService.content_hash(stream)
        assert stream.read() == b"payload"
