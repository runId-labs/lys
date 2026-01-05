"""
File storage utilities for S3-compatible object storage.
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional, BinaryIO, Union

import aioboto3
import boto3
from botocore.client import Config

logger = logging.getLogger("lys.storage")


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, operation: str, original_error: Optional[Exception] = None):
        self.message = message
        self.operation = operation
        self.original_error = original_error
        super().__init__(f"{operation}: {message}")


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def upload(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload data to storage.

        Args:
            path: Destination path in storage
            data: File content as bytes or file-like object
            content_type: MIME type of the file

        Returns:
            The path where the file was stored
        """
        pass

    @abstractmethod
    async def upload_file(self, path: str, local_file_path: str) -> str:
        """
        Upload a local file to storage.

        Args:
            path: Destination path in storage
            local_file_path: Path to local file

        Returns:
            The path where the file was stored
        """
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """
        Download file content from storage.

        Args:
            path: Path to the file in storage

        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        """
        Delete a file from storage.

        Args:
            path: Path to the file in storage
        """
        pass

    @abstractmethod
    async def get_presigned_url(self, path: str, expires_in: int = 300) -> str:
        """
        Generate a presigned URL for temporary access.

        Args:
            path: Path to the file in storage
            expires_in: URL expiration time in seconds

        Returns:
            Presigned URL string
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            path: Path to the file in storage

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_presigned_upload_url(
        self,
        path: str,
        content_type: Optional[str] = None,
        expires_in: int = 300
    ) -> str:
        """
        Generate a presigned URL for uploading a file.

        Args:
            path: Destination path in storage
            content_type: Expected MIME type of the file
            expires_in: URL expiration time in seconds

        Returns:
            Presigned URL string for PUT request
        """
        pass

    # Sync versions for Celery workers

    @abstractmethod
    def upload_sync(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> str:
        """Synchronous version of upload."""
        pass

    @abstractmethod
    def upload_file_sync(self, path: str, local_file_path: str) -> str:
        """Synchronous version of upload_file."""
        pass

    @abstractmethod
    def download_sync(self, path: str) -> bytes:
        """Synchronous version of download."""
        pass

    @abstractmethod
    def delete_sync(self, path: str) -> None:
        """Synchronous version of delete."""
        pass

    @abstractmethod
    def get_presigned_url_sync(self, path: str, expires_in: int = 300) -> str:
        """Synchronous version of get_presigned_url."""
        pass


class S3StorageBackend(StorageBackend):
    """
    S3-compatible storage backend.

    Supports AWS S3, MinIO, and other S3-compatible services.
    """

    def __init__(self, config: dict):
        """
        Initialize S3 storage backend.

        Args:
            config: Configuration dict with keys:
                - bucket: S3 bucket name (required)
                - access_key: AWS access key ID (required)
                - secret_key: AWS secret access key (required)
                - region: AWS region (default: "eu-west-1")
                - endpoint_url: Custom endpoint for S3-compatible services (optional)
                - api_version: S3 API version (optional)
        """
        self.bucket = config["bucket"]
        self.access_key = config["access_key"]
        self.secret_key = config["secret_key"]
        self.region = config.get("region", "eu-west-1")
        self.endpoint_url = config.get("endpoint_url")
        self.api_version = config.get("api_version")

        self._async_session = aioboto3.Session()
        self._sync_session = boto3.session.Session()

    def _get_client_config(self) -> dict:
        """Get common client configuration."""
        return {
            "api_version": self.api_version,
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "config": Config(signature_version="s3v4"),
            "region_name": self.region,
        }

    # Async methods

    async def upload(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> str:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type

                if isinstance(data, bytes):
                    await client.put_object(
                        Bucket=self.bucket,
                        Key=path,
                        Body=data,
                        **extra_args
                    )
                else:
                    await client.upload_fileobj(
                        data,
                        self.bucket,
                        path,
                        ExtraArgs=extra_args if extra_args else None
                    )
            return path
        except Exception as ex:
            logger.error(f"S3 upload error: {ex}")
            raise StorageError(str(ex), "upload", ex)

    async def upload_file(self, path: str, local_file_path: str) -> str:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                await client.upload_file(local_file_path, self.bucket, path)
            return path
        except Exception as ex:
            logger.error(f"S3 upload_file error: {ex}")
            raise StorageError(str(ex), "upload_file", ex)

    async def download(self, path: str) -> bytes:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                response = await client.get_object(Bucket=self.bucket, Key=path)
                async with response["Body"] as stream:
                    return await stream.read()
        except Exception as ex:
            logger.error(f"S3 download error: {ex}")
            raise StorageError(str(ex), "download", ex)

    async def delete(self, path: str) -> None:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                await client.delete_object(Bucket=self.bucket, Key=path)
        except Exception as ex:
            logger.error(f"S3 delete error: {ex}")
            raise StorageError(str(ex), "delete", ex)

    async def get_presigned_url(self, path: str, expires_in: int = 300) -> str:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": path},
                    ExpiresIn=expires_in
                )
            return url
        except Exception as ex:
            logger.error(f"S3 presigned URL error: {ex}")
            raise StorageError(str(ex), "get_presigned_url", ex)

    async def exists(self, path: str) -> bool:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                await client.head_object(Bucket=self.bucket, Key=path)
                return True
        except Exception as ex:
            error_code = getattr(ex, "response", {}).get("Error", {}).get("Code")
            if error_code == "404":
                return False
            logger.error(f"S3 exists error: {ex}")
            raise StorageError(str(ex), "exists", ex)

    async def get_presigned_upload_url(
        self,
        path: str,
        content_type: Optional[str] = None,
        expires_in: int = 300
    ) -> str:
        try:
            async with self._async_session.client("s3", **self._get_client_config()) as client:
                params = {"Bucket": self.bucket, "Key": path}
                if content_type:
                    params["ContentType"] = content_type
                url = await client.generate_presigned_url(
                    "put_object",
                    Params=params,
                    ExpiresIn=expires_in
                )
            return url
        except Exception as ex:
            logger.error(f"S3 presigned upload URL error: {ex}")
            raise StorageError(str(ex), "get_presigned_upload_url", ex)

    # Sync methods for Celery workers

    def upload_sync(
        self,
        path: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None
    ) -> str:
        try:
            client = self._sync_session.client("s3", **self._get_client_config())
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            if isinstance(data, bytes):
                client.put_object(
                    Bucket=self.bucket,
                    Key=path,
                    Body=data,
                    **extra_args
                )
            else:
                client.upload_fileobj(
                    data,
                    self.bucket,
                    path,
                    ExtraArgs=extra_args if extra_args else None
                )
            return path
        except Exception as ex:
            logger.error(f"S3 upload_sync error: {ex}")
            raise StorageError(str(ex), "upload_sync", ex)

    def upload_file_sync(self, path: str, local_file_path: str) -> str:
        try:
            client = self._sync_session.client("s3", **self._get_client_config())
            client.upload_file(local_file_path, self.bucket, path)
            return path
        except Exception as ex:
            logger.error(f"S3 upload_file_sync error: {ex}")
            raise StorageError(str(ex), "upload_file_sync", ex)

    def download_sync(self, path: str) -> bytes:
        try:
            client = self._sync_session.client("s3", **self._get_client_config())
            response = client.get_object(Bucket=self.bucket, Key=path)
            return response["Body"].read()
        except Exception as ex:
            logger.error(f"S3 download_sync error: {ex}")
            raise StorageError(str(ex), "download_sync", ex)

    def delete_sync(self, path: str) -> None:
        try:
            client = self._sync_session.client("s3", **self._get_client_config())
            client.delete_object(Bucket=self.bucket, Key=path)
        except Exception as ex:
            logger.error(f"S3 delete_sync error: {ex}")
            raise StorageError(str(ex), "delete_sync", ex)

    def get_presigned_url_sync(self, path: str, expires_in: int = 300) -> str:
        try:
            client = self._sync_session.client("s3", **self._get_client_config())
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expires_in
            )
            return url
        except Exception as ex:
            logger.error(f"S3 presigned_url_sync error: {ex}")
            raise StorageError(str(ex), "get_presigned_url_sync", ex)


# Backend registry for future extensibility
_BACKENDS = {
    "s3": S3StorageBackend,
}


def get_storage_backend(config: dict) -> StorageBackend:
    """
    Factory function to get a storage backend instance.

    Args:
        config: Configuration dict with "backend" key specifying the backend type
                and additional backend-specific configuration.

    Returns:
        Configured StorageBackend instance

    Raises:
        ValueError: If backend type is not supported

    Example:
        config = {
            "backend": "s3",
            "bucket": "my-bucket",
            "access_key": "...",
            "secret_key": "...",
            "region": "eu-west-1",
        }
        storage = get_storage_backend(config)
    """
    backend_type = config.get("backend", "s3")

    if backend_type not in _BACKENDS:
        raise ValueError(
            f"Unsupported storage backend: {backend_type}. "
            f"Supported backends: {list(_BACKENDS.keys())}"
        )

    return _BACKENDS[backend_type](config)