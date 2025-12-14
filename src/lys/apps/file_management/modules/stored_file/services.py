import logging
from typing import Any, Optional, Union, BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.file_management.modules.stored_file.consts import (
    FILE_STORAGE_PLUGIN_KEY,
    DEFAULT_PRESIGNED_URL_EXPIRES,
)
from lys.apps.file_management.modules.stored_file.entities import (
    StoredFile,
    StoredFileMimeType,
    StoredFileType,
)
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.storage import get_storage_backend, StorageBackend

logger = logging.getLogger(__name__)


@register_service()
class StoredFileMimeTypeService(EntityService[StoredFileMimeType]):
    pass


@register_service()
class StoredFileTypeService(EntityService[StoredFileType]):
    pass


@register_service()
class StoredFileService(EntityService[StoredFile]):
    """Service for managing stored files with S3 backend."""

    _storage_backend: Optional[StorageBackend] = None

    @classmethod
    def get_storage_backend(cls) -> StorageBackend:
        """Get or create the storage backend instance."""
        if cls._storage_backend is None:
            config = cls.app_manager.settings.get_plugin_config(FILE_STORAGE_PLUGIN_KEY)
            if not config:
                raise ValueError(
                    f"File storage plugin not configured. "
                    f"Add '{FILE_STORAGE_PLUGIN_KEY}' to settings.plugins"
                )
            cls._storage_backend = get_storage_backend(config)
        return cls._storage_backend

    @classmethod
    async def upload(
        cls,
        session: AsyncSession,
        data: Union[bytes, BinaryIO],
        original_name: str,
        size: int,
        mime_type_id: str,
        type_id: str,
        extra_data: Optional[dict[str, Any]] = None,
    ) -> StoredFile:
        """
        Upload a file to S3 and create database record.

        Args:
            session: Database session
            data: File content as bytes or file-like object
            original_name: Original filename
            size: File size in bytes
            mime_type_id: MIME type ID (e.g., "image/png")
            type_id: File type ID (e.g., "USER_IMPORT_FILE")
            extra_data: Additional metadata

        Returns:
            Created StoredFile entity
        """
        # Create DB record first to get ID for path generation
        stored_file = await cls.create(
            session,
            original_name=original_name,
            size=size,
            mime_type_id=mime_type_id,
            type_id=type_id,
            extra_data=extra_data,
        )

        # Flush to ensure created_at is set (needed for storage_name)
        await session.flush()

        # Upload to S3
        storage = cls.get_storage_backend()
        try:
            await storage.upload(
                path=stored_file.path,
                data=data,
                content_type=mime_type_id,
            )
            logger.info(f"File uploaded to S3: {stored_file.path}")
        except Exception as ex:
            logger.error(f"Failed to upload file to S3: {ex}")
            await session.delete(stored_file)
            raise

        return stored_file

    @classmethod
    async def download(cls, stored_file: StoredFile) -> bytes:
        """
        Download file content from S3.

        Args:
            stored_file: StoredFile entity

        Returns:
            File content as bytes
        """
        storage = cls.get_storage_backend()
        return await storage.download(stored_file.path)

    @classmethod
    async def delete_file(cls, session: AsyncSession, stored_file: StoredFile) -> None:
        """
        Delete file from S3 and database.

        Args:
            session: Database session
            stored_file: StoredFile entity to delete
        """
        storage = cls.get_storage_backend()

        # Delete from S3 first
        try:
            await storage.delete(stored_file.path)
            logger.info(f"File deleted from S3: {stored_file.path}")
        except Exception as ex:
            logger.error(f"Failed to delete file from S3: {ex}")
            raise

        # Delete from DB
        await session.delete(stored_file)

    @classmethod
    async def get_presigned_url(
        cls,
        stored_file: StoredFile,
        expires_in: int = DEFAULT_PRESIGNED_URL_EXPIRES,
    ) -> str:
        """
        Generate a presigned URL for temporary file access.

        Args:
            stored_file: StoredFile entity
            expires_in: URL expiration time in seconds (default: 300)

        Returns:
            Presigned URL string
        """
        storage = cls.get_storage_backend()
        return await storage.get_presigned_url(stored_file.path, expires_in)

    # Sync methods for Celery workers

    @classmethod
    def upload_sync(
        cls,
        original_name: str,
        size: int,
        mime_type_id: str,
        type_id: str,
        data: Union[bytes, BinaryIO],
        extra_data: Optional[dict[str, Any]] = None,
    ) -> StoredFile:
        """
        Synchronous version of upload for Celery workers.

        Returns:
            Created StoredFile entity
        """
        storage = cls.get_storage_backend()

        with cls.app_manager.database.get_sync_session() as session:
            stored_file = cls.entity_class(
                original_name=original_name,
                size=size,
                mime_type_id=mime_type_id,
                type_id=type_id,
                extra_data=extra_data,
            )
            session.add(stored_file)
            session.flush()

            try:
                storage.upload_sync(
                    path=stored_file.path,
                    data=data,
                    content_type=mime_type_id,
                )
                logger.info(f"File uploaded to S3 (sync): {stored_file.path}")
                session.commit()
            except Exception as ex:
                logger.error(f"Failed to upload file to S3 (sync): {ex}")
                session.rollback()
                raise

            return stored_file

    @classmethod
    def download_sync(cls, stored_file: StoredFile) -> bytes:
        """Synchronous version of download for Celery workers."""
        storage = cls.get_storage_backend()
        return storage.download_sync(stored_file.path)

    @classmethod
    def delete_file_sync(cls, stored_file: StoredFile) -> None:
        """Synchronous version of delete_file for Celery workers."""
        storage = cls.get_storage_backend()

        with cls.app_manager.database.get_sync_session() as session:
            try:
                storage.delete_sync(stored_file.path)
                logger.info(f"File deleted from S3 (sync): {stored_file.path}")

                db_file = session.get(cls.entity_class, stored_file.id)
                if db_file:
                    session.delete(db_file)
                    session.commit()
            except Exception as ex:
                logger.error(f"Failed to delete file (sync): {ex}")
                session.rollback()
                raise

    @classmethod
    def get_presigned_url_sync(
        cls,
        stored_file: StoredFile,
        expires_in: int = DEFAULT_PRESIGNED_URL_EXPIRES,
    ) -> str:
        """Synchronous version of get_presigned_url for Celery workers."""
        storage = cls.get_storage_backend()
        return storage.get_presigned_url_sync(stored_file.path, expires_in)
