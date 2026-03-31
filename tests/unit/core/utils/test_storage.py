"""
Unit tests for S3StorageBackend: head_object, download_range, and their sync variants.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lys.core.utils.storage import S3StorageBackend, StorageError


@pytest.fixture
def s3_config():
    return {
        "bucket": "test-bucket",
        "access_key": "test-key",
        "secret_key": "test-secret",
        "region": "eu-west-1",
    }


@pytest.fixture
def backend(s3_config):
    return S3StorageBackend(s3_config)


class TestHeadObject:
    """Tests for async head_object."""

    @pytest.mark.asyncio
    async def test_returns_size_and_content_type(self, backend):
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/pdf",
        }
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            result = await backend.head_object("files/doc.pdf")

        assert result == {"size": 1024, "content_type": "application/pdf"}
        mock_client.head_object.assert_called_once_with(Bucket="test-bucket", Key="files/doc.pdf")

    @pytest.mark.asyncio
    async def test_defaults_when_fields_missing(self, backend):
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            result = await backend.head_object("files/empty.bin")

        assert result == {"size": 0, "content_type": ""}

    @pytest.mark.asyncio
    async def test_raises_storage_error_on_failure(self, backend):
        mock_client = AsyncMock()
        mock_client.head_object.side_effect = Exception("Not Found")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            with pytest.raises(StorageError, match="head_object"):
                await backend.head_object("missing/file.txt")


class TestDownloadRange:
    """Tests for async download_range."""

    @pytest.mark.asyncio
    async def test_downloads_byte_range(self, backend):
        mock_stream = AsyncMock()
        mock_stream.read.return_value = b"partial content"
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get_object.return_value = {"Body": mock_stream}
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            result = await backend.download_range("files/large.bin", 100, 200)

        assert result == b"partial content"
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="files/large.bin", Range="bytes=100-200"
        )

    @pytest.mark.asyncio
    async def test_validates_negative_start(self, backend):
        with pytest.raises(ValueError, match="Invalid byte range"):
            await backend.download_range("file.bin", -1, 100)

    @pytest.mark.asyncio
    async def test_validates_end_less_than_start(self, backend):
        with pytest.raises(ValueError, match="Invalid byte range"):
            await backend.download_range("file.bin", 200, 100)

    @pytest.mark.asyncio
    async def test_allows_equal_start_and_end(self, backend):
        mock_stream = AsyncMock()
        mock_stream.read.return_value = b"x"
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get_object.return_value = {"Body": mock_stream}
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            result = await backend.download_range("file.bin", 50, 50)

        assert result == b"x"
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="file.bin", Range="bytes=50-50"
        )

    @pytest.mark.asyncio
    async def test_allows_zero_start(self, backend):
        mock_stream = AsyncMock()
        mock_stream.read.return_value = b"start"
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)

        mock_client = AsyncMock()
        mock_client.get_object.return_value = {"Body": mock_stream}
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            result = await backend.download_range("file.bin", 0, 10)

        assert result == b"start"

    @pytest.mark.asyncio
    async def test_raises_storage_error_on_s3_failure(self, backend):
        mock_client = AsyncMock()
        mock_client.get_object.side_effect = Exception("Access Denied")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(backend._async_session, "client", return_value=mock_client):
            with pytest.raises(StorageError, match="download_range"):
                await backend.download_range("file.bin", 0, 100)


class TestHeadObjectSync:
    """Tests for synchronous head_object_sync."""

    def test_returns_size_and_content_type(self, backend):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 2048,
            "ContentType": "image/png",
        }

        with patch.object(backend._sync_session, "client", return_value=mock_client):
            result = backend.head_object_sync("images/photo.png")

        assert result == {"size": 2048, "content_type": "image/png"}
        mock_client.head_object.assert_called_once_with(Bucket="test-bucket", Key="images/photo.png")

    def test_defaults_when_fields_missing(self, backend):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}

        with patch.object(backend._sync_session, "client", return_value=mock_client):
            result = backend.head_object_sync("file.bin")

        assert result == {"size": 0, "content_type": ""}

    def test_raises_storage_error_on_failure(self, backend):
        mock_client = MagicMock()
        mock_client.head_object.side_effect = Exception("Timeout")

        with patch.object(backend._sync_session, "client", return_value=mock_client):
            with pytest.raises(StorageError, match="head_object_sync"):
                backend.head_object_sync("file.bin")


class TestDownloadRangeSync:
    """Tests for synchronous download_range_sync."""

    def test_downloads_byte_range(self, backend):
        mock_body = MagicMock()
        mock_body.read.return_value = b"chunk data"

        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": mock_body}

        with patch.object(backend._sync_session, "client", return_value=mock_client):
            result = backend.download_range_sync("files/data.bin", 0, 99)

        assert result == b"chunk data"
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="files/data.bin", Range="bytes=0-99"
        )

    def test_validates_negative_start(self, backend):
        with pytest.raises(ValueError, match="Invalid byte range"):
            backend.download_range_sync("file.bin", -5, 10)

    def test_validates_end_less_than_start(self, backend):
        with pytest.raises(ValueError, match="Invalid byte range"):
            backend.download_range_sync("file.bin", 100, 50)

    def test_raises_storage_error_on_s3_failure(self, backend):
        mock_client = MagicMock()
        mock_client.get_object.side_effect = Exception("Network error")

        with patch.object(backend._sync_session, "client", return_value=mock_client):
            with pytest.raises(StorageError, match="download_range_sync"):
                backend.download_range_sync("file.bin", 0, 100)