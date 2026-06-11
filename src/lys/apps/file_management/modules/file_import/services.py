"""
File import services for processing CSV/Excel imports.
"""
import abc
import logging
import zipfile
from io import BytesIO
from typing import Any, Callable, Optional, Type, Hashable

from pandas import read_csv, read_excel, DataFrame
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_PROCESSING,
    FILE_IMPORT_STATUS_COMPLETED,
    FILE_IMPORT_STATUS_FAILED,
    FILE_IMPORT_STATUS_SKIPPED,
    REPORT_MESSAGE_NO_FILE,
    CSV_MIME_TYPE,
    XLS_MIME_TYPE,
    XLSX_MIME_TYPE,
)
from lys.core.utils.zip import extract_zip_files, ZipExtractionError
from lys.apps.file_management.modules.file_import.entities import (
    FileImport,
    FileImportType,
    FileImportStatus,
)
from lys.apps.file_management.modules.file_import.models import (
    ImportColumn,
    ImportMessage,
    ImportReport,
    ImportConfig,
)
from lys.core.entities import Entity
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc

logger = logging.getLogger(__name__)


@register_service()
class FileImportTypeService(EntityService[FileImportType]):
    pass


@register_service()
class FileImportStatusService(EntityService[FileImportStatus]):
    pass


@register_service()
class FileImportService(EntityService[FileImport]):
    """Service for managing FileImport entities."""

    @classmethod
    def find_active_import(cls, session: Session, client_id: str, content_hash: str):
        """Content-hash idempotency: an existing non-failed import of the same file.

        Returns the most recent FileImport for this client whose StoredFile has the same
        ``content_hash`` and whose status is PROCESSING or COMPLETED — i.e. the content is
        already being imported or has been imported. FAILED/SKIPPED/CANCELLED imports are
        ignored, so a re-import after a failure is always allowed.

        Callers decide whether to apply this check (per import nature); the engine is generic.
        Returns None when content_hash is falsy or no match exists.
        """
        if not content_hash:
            return None
        file_import = cls.entity_class
        stored_file = cls.app_manager.get_entity("stored_file")
        stmt = (
            select(file_import)
            .join(stored_file, stored_file.id == file_import.stored_file_id)
            .where(
                file_import.client_id == client_id,
                stored_file.content_hash == content_hash,
                file_import.status_id.in_([FILE_IMPORT_STATUS_PROCESSING, FILE_IMPORT_STATUS_COMPLETED]),
            )
            .order_by(file_import.created_at.desc())
        )
        return session.execute(stmt).scalars().first()

    @classmethod
    def stage_zip_documents(
        cls,
        stored_file_id: str,
        *,
        per_file_type_id: str,
        import_type_id: str,
        check_idempotency: bool = False,
        max_files: Optional[int] = None,
        mime_resolver: Optional[Callable[[str], str]] = None,
        per_file_extra_data: Optional[Callable[[Any, str], dict]] = None,
        stored_file_fields: Optional[Callable[[Any, str], dict]] = None,
        file_import_fields: Optional[Callable[[Any, str], dict]] = None,
    ) -> dict:
        """Generic ZIP import staging: one StoredFile + FileImport per extracted document.

        Shared skeleton for every ZIP-based import (DSN / FEC / juridical / ...): downloads
        the ZIP, extracts it (path-traversal / zip-bomb safe), and for each document creates
        a StoredFile (content hash computed by upload) + a PENDING FileImport. The CALLER
        then schedules its per-document task for the returned ``staged`` ids and handles
        notifications — that part (chord vs delay, notifs) is import-specific and stays out.

        ``check_idempotency`` is the per-import-nature policy (NOT a user flag): when on, a
        document whose content hash matches a non-failed import (existing or earlier in this
        same ZIP) is NOT re-imported — a SKIPPED FileImport is recorded instead (pointing at
        the original via ``extra_data["skipped_duplicate_of"]``), and no S3 upload happens.

        Idempotency is BEST-EFFORT, not a hard guarantee: the check + insert is not atomic and
        there is no unique constraint on (client_id, content_hash). Two imports of the same
        content running concurrently can both pass and create two PROCESSING rows (the in-batch
        ``seen`` map only deduplicates within a single ZIP). It covers the real case (sequential
        re-imports); a hard guarantee would need a partial unique index + IntegrityError->SKIPPED.

        Args:
            stored_file_id: the ZIP StoredFile id.
            per_file_type_id: StoredFile type for each extracted document.
            import_type_id: FileImport type_id.
            check_idempotency: apply content-hash idempotency (skip duplicates).
            max_files: reject the whole batch if it holds more documents (no silent truncation).
            mime_resolver: filename -> mime type (default application/octet-stream).
            per_file_extra_data: (zip_stored_file, filename) -> extra_data dict for the document.
            stored_file_fields: (zip_stored_file, filename) -> extra StoredFile columns (subclass
                fields, forwarded opaque to the upload).
            file_import_fields: (zip_stored_file, filename) -> extra FileImport columns (subclass
                fields, forwarded opaque to the FileImport).

        Returns:
            {"zip_file_id", "staged": [file_import_id...], "skipped": [...], "errors": [...]}.
        """
        app_manager = cls.app_manager
        stored_file_service = app_manager.get_service("stored_file")
        result: dict = {"zip_file_id": stored_file_id, "staged": [], "skipped": [], "errors": []}
        seen: dict = {}  # content_hash -> file_import_id staged earlier in THIS batch

        try:
            with app_manager.database.get_sync_session() as session:
                zip_file = session.get(stored_file_service.entity_class, stored_file_id)
                if not zip_file:
                    result["errors"].append(f"StoredFile not found: {stored_file_id}")
                    return result
                client_id = zip_file.client_id

                zip_content = stored_file_service.download_sync(zip_file)
                # Enforce max_files DURING extraction (reject early, bound memory) — not
                # post-hoc; None falls back to extract_zip_files' own default.
                extract_kwargs = {} if max_files is None else {"max_files": max_files}
                try:
                    zip_files = list(extract_zip_files(zip_content, **extract_kwargs))
                except (ZipExtractionError, zipfile.BadZipFile) as e:
                    result["errors"].append(f"ZIP extraction failed: {e}")
                    return result

                for filename, file_content in zip_files:
                    try:
                        mime_type = mime_resolver(filename) if mime_resolver else "application/octet-stream"
                        extra = per_file_extra_data(zip_file, filename) if per_file_extra_data else {}
                        sf_fields = stored_file_fields(zip_file, filename) if stored_file_fields else {}
                        fi_fields = file_import_fields(zip_file, filename) if file_import_fields else {}
                        content_hash = stored_file_service.content_hash(file_content)

                        if check_idempotency and content_hash:
                            existing = cls.find_active_import(session, client_id, content_hash)
                            # Prefer the in-batch original (id known) over the DB one.
                            duplicate_of = seen.get(content_hash) or (str(existing.id) if existing else None)
                            if duplicate_of:
                                skipped = cls.entity_class(
                                    client_id=client_id, stored_file_id=None, type_id=import_type_id,
                                    status_id=FILE_IMPORT_STATUS_SKIPPED,
                                    extra_data={**extra, "original_file_name": filename,
                                                "content_hash": content_hash,
                                                "skipped_duplicate_of": duplicate_of},
                                    **fi_fields)
                                session.add(skipped)
                                session.flush()
                                result["skipped"].append({"name": filename, "duplicate_of": duplicate_of})
                                continue

                        doc_file = stored_file_service.upload_sync(
                            client_id=client_id, original_name=filename, size=len(file_content),
                            mime_type=mime_type, type_id=per_file_type_id, data=file_content,
                            extra_data=extra, **sf_fields)
                        file_import = cls.entity_class(
                            client_id=client_id, stored_file_id=str(doc_file.id), type_id=import_type_id,
                            status_id=FILE_IMPORT_STATUS_PENDING, extra_data=extra, **fi_fields)
                        session.add(file_import)
                        session.flush()
                        if content_hash:
                            seen[content_hash] = str(file_import.id)
                        result["staged"].append(str(file_import.id))
                    except Exception as e:  # noqa: BLE001 — one bad doc must not abort the batch
                        result["errors"].append(f"Failed to process {filename}: {e}")
                        logger.error(f"stage_zip_documents: failed on {filename}: {e}")

                # Delete the ZIP only when every document was staged without error.
                if not result["errors"]:
                    try:
                        stored_file_service.delete_file_sync(zip_file)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"Failed to delete ZIP {stored_file_id}: {e}")
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"Failed to process ZIP: {e}")
            logger.error(f"stage_zip_documents: ZIP {stored_file_id} failed: {e}")
        return result

    @classmethod
    async def create_import(
        cls,
        session: AsyncSession,
        stored_file_id: str,
        type_id: str,
        config: ImportConfig | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> FileImport:
        """
        Create a new file import job.

        Args:
            session: Database session
            stored_file_id: ID of the StoredFile to import
            type_id: Import type (e.g., USER_IMPORT)
            config: Import configuration
            extra_data: Additional metadata

        Returns:
            Created FileImport entity
        """
        return await cls.create(
            session,
            stored_file_id=stored_file_id,
            type_id=type_id,
            status_id=FILE_IMPORT_STATUS_PENDING,
            config=config.to_dict() if config else None,
            extra_data=extra_data,
        )

    @classmethod
    def update_progress(
        cls,
        file_import: FileImport,
        status_id: str,
        report: ImportReport | None = None,
        total_rows: int | None = None,
        processed_rows: int | None = None,
        success_rows: int | None = None,
        error_rows: int | None = None,
    ) -> None:
        """
        Update import progress (in-place, caller must commit).

        Args:
            file_import: FileImport entity to update
            status_id: New status
            report: Import report
            total_rows: Total rows in file
            processed_rows: Rows processed so far
            success_rows: Rows imported successfully
            error_rows: Rows with errors
        """
        file_import.status_id = status_id

        if report is not None:
            file_import.errors = report.to_dict()

        if total_rows is not None:
            file_import.total_rows = total_rows

        if processed_rows is not None:
            file_import.processed_rows = processed_rows

        if success_rows is not None:
            file_import.success_rows = success_rows

        if error_rows is not None:
            file_import.error_rows = error_rows

        if status_id == FILE_IMPORT_STATUS_PROCESSING and file_import.started_at is None:
            file_import.started_at = now_utc()

        if status_id in (FILE_IMPORT_STATUS_COMPLETED, FILE_IMPORT_STATUS_FAILED):
            file_import.completed_at = now_utc()


class AbstractImportService(abc.ABC):
    """
    Abstract base class for implementing file imports.

    Subclass this to create specific import handlers (e.g., UserImportService).

    Example:
        class UserImportService(AbstractImportService):
            import_type = "USER_IMPORT"

            def get_column_mapping(self) -> dict[str, ImportColumn]:
                return {
                    "email": ImportColumn(
                        is_optional=False,
                        validator=lambda x: "@" in str(x),
                        setter=lambda entity, value, session: setattr(entity, "email", value),
                    ),
                    "name": ImportColumn(
                        is_optional=True,
                        validator=lambda x: True,
                        setter=lambda entity, value, session: setattr(entity, "name", value),
                    ),
                }

            def init_entity(self, unique_value: Any, session: Session) -> Entity:
                # Find existing or create new
                user = session.query(User).filter_by(email=unique_value).first()
                return user or User()
    """

    # Override in subclass: the import type ID (e.g., "USER_IMPORT")
    import_type: str = None

    # Override in subclass: the unique column used to identify existing entities
    unique_column: str = None

    # Set to False in subclass to keep files after import
    delete_file_after_import: bool = True

    # Pandas readers for supported MIME types
    READER_MAPPING = {
        CSV_MIME_TYPE: read_csv,
        XLS_MIME_TYPE: read_excel,
        XLSX_MIME_TYPE: read_excel,
    }

    def __init__(self, app_manager):
        """
        Initialize the import service.

        Args:
            app_manager: Lys AppManager instance
        """
        self.app_manager = app_manager

    @abc.abstractmethod
    def get_column_mapping(self) -> dict[str, ImportColumn]:
        """
        Define the column mapping for this import type.

        Returns:
            Dict mapping column names to ImportColumn definitions
        """
        raise NotImplementedError

    @abc.abstractmethod
    def init_entity(self, unique_value: Any, session: Session) -> Entity:
        """
        Initialize or find an entity for the given unique value.

        Args:
            unique_value: Value from the unique column
            session: Database session

        Returns:
            New or existing entity instance
        """
        raise NotImplementedError

    def parse_file(
        self,
        file_import: FileImport,
        raw_content: bytes,
        config: ImportConfig,
    ) -> DataFrame:
        """
        Parse raw file content into a DataFrame.

        Override this method for custom file formats (DSN, XML, fixed-width, etc.).
        Default implementation uses pandas readers for CSV/Excel based on MIME type.

        Args:
            file_import: FileImport entity
            raw_content: Raw file content as bytes
            config: Import configuration

        Returns:
            DataFrame ready for processing

        Raises:
            ValueError: If MIME type is not supported
        """
        mime_type = file_import.stored_file.mime_type
        if mime_type not in self.READER_MAPPING:
            raise ValueError(f"Unsupported MIME type: {mime_type}")

        reader = self.READER_MAPPING[mime_type]
        buffer = BytesIO(raw_content)

        if mime_type == CSV_MIME_TYPE:
            return reader(buffer, delimiter=config.delimiter, encoding=config.encoding)
        return reader(buffer)

    def prepare_import(
        self,
        file_import: FileImport,
        df: DataFrame,
        session: Session,
    ) -> DataFrame:
        """
        Prepare data before row processing.

        Override this method to:
        - Fetch or create related entities (e.g., company, establishments)
        - Enrich DataFrame with foreign keys
        - Transform or normalize data
        - Validate business rules

        Args:
            file_import: FileImport entity
            df: DataFrame from parse_file
            session: Database session

        Returns:
            Modified DataFrame ready for row processing
        """
        return df

    def on_import_start(self, file_import: FileImport, session: Session) -> None:
        """Hook called when import starts. Override for custom logic."""
        pass

    def on_import_end(self, file_import: FileImport, session: Session) -> None:
        """Hook called when import ends. Override for custom logic."""
        pass

    def on_row_success(self, entity: Entity, row_index: int, session: Session) -> None:
        """Hook called after a row is successfully imported. Override for custom logic."""
        pass

    def on_row_error(self, row_index: int, errors: dict[str, ImportMessage], session: Session) -> None:
        """Hook called when a row has errors. Override for custom logic."""
        pass

    def _get_stored_file_service(self):
        """Get the StoredFileService."""
        return self.app_manager.get_service("stored_file")

    def _get_file_import_service(self) -> Type[FileImportService]:
        """Get the FileImportService."""
        return self.app_manager.get_service("file_import")

    def _check_headers(self, df: DataFrame, report: ImportReport) -> list[str]:
        """
        Validate DataFrame headers against column mapping.

        Args:
            df: Pandas DataFrame
            report: Import report to update

        Returns:
            List of valid headers
        """
        headers = list(df.columns)
        column_mapping = self.get_column_mapping()

        # Check for missing required columns
        for column_name, column_def in column_mapping.items():
            if column_name not in headers and not column_def.is_optional:
                report.add_header_error(column_name, ImportMessage.missing())

        # Warn about unknown columns
        for header in headers:
            if header not in column_mapping:
                report.add_header_error(header, ImportMessage.unknown())

        return headers

    def _process_row(
        self,
        headers: list[str],
        row: Any,
        row_index: Hashable,
        report: ImportReport,
        session: Session,
    ) -> bool:
        """
        Process a single row from the DataFrame.

        Args:
            headers: Column headers
            row: Row data
            row_index: Row index
            report: Import report
            session: Database session

        Returns:
            True if row was processed successfully
        """
        column_mapping = self.get_column_mapping()

        # Get or create entity
        unique_value = row[self.unique_column] if self.unique_column in headers else None
        entity = self.init_entity(unique_value, session)

        row_has_error = False

        for header in headers:
            column_def = column_mapping.get(header)
            if column_def is None:
                continue

            # Skip unique column on updates (entity already identified)
            if entity.id is not None and header == self.unique_column:
                continue

            value = row[header]

            # Validate value
            if not column_def.validator(value):
                report.add_row_error(row_index, header, ImportMessage.wrong_format(str(value)))
                row_has_error = True
                continue

            # Apply value to entity
            try:
                column_def.setter(entity, value, session)
            except Exception as ex:
                logger.error(f"Error setting {header} on row {row_index}: {ex}")
                report.add_row_error(row_index, header, ImportMessage.internal_error(str(ex)))
                row_has_error = True

        if row_has_error:
            self.on_row_error(row_index, report.rows.get(row_index, {}), session)
            return False

        # Add new entity to session
        if entity.id is None:
            session.add(entity)

        self.on_row_success(entity, row_index, session)
        return True

    def _process_dataframe(
        self,
        file_import: FileImport,
        df: DataFrame,
        report: ImportReport,
        session: Session,
    ) -> None:
        """
        Process the entire DataFrame.

        Args:
            file_import: FileImport entity
            df: Pandas DataFrame
            report: Import report
            session: Database session
        """
        file_import_service = self._get_file_import_service()

        # Check headers
        headers = self._check_headers(df, report)

        if report.has_blocking_error:
            file_import_service.update_progress(
                file_import,
                FILE_IMPORT_STATUS_FAILED,
                report=report,
            )
            return

        # Start processing
        total_rows = len(df.index)
        file_import_service.update_progress(
            file_import,
            FILE_IMPORT_STATUS_PROCESSING,
            report=report,
            total_rows=total_rows,
            processed_rows=0,
            success_rows=0,
            error_rows=0,
        )

        self.on_import_start(file_import, session)

        success_count = 0
        error_count = 0

        for row_index, row in df.iterrows():
            if self._process_row(headers, row, row_index, report, session):
                success_count += 1
            else:
                error_count += 1

            # Update progress
            file_import_service.update_progress(
                file_import,
                FILE_IMPORT_STATUS_PROCESSING,
                report=report,
                processed_rows=row_index + 1,
                success_rows=success_count,
                error_rows=error_count,
            )

        # Complete import
        final_status = FILE_IMPORT_STATUS_COMPLETED if error_count == 0 else FILE_IMPORT_STATUS_FAILED
        file_import_service.update_progress(
            file_import,
            final_status,
            report=report,
            success_rows=success_count,
            error_rows=error_count,
        )

        self.on_import_end(file_import, session)

    def perform_import(self, file_import_id: str) -> None:
        """
        Execute the import process.

        This is the main entry point, typically called from a Celery task.

        Args:
            file_import_id: ID of the FileImport to process
        """
        file_import_service = self._get_file_import_service()
        stored_file_service = self._get_stored_file_service()

        with self.app_manager.database.get_sync_session() as session:
            # Load FileImport
            file_import = session.get(file_import_service.entity_class, file_import_id)
            if file_import is None:
                logger.error(f"FileImport {file_import_id} not found")
                return

            report = ImportReport()

            # Check stored file exists
            if file_import.stored_file is None:
                report.add_global_error(REPORT_MESSAGE_NO_FILE)
                file_import_service.update_progress(
                    file_import,
                    FILE_IMPORT_STATUS_FAILED,
                    report=report,
                )
                session.commit()
                return

            try:
                # Download raw file content
                raw_content = stored_file_service.download_sync(file_import.stored_file)

                # Parse config
                config = ImportConfig.from_dict(file_import.config or {})

                # Parse file into DataFrame (can be overridden for custom formats)
                df = self.parse_file(file_import, raw_content, config)

                # Prepare import (fetch/create related entities, enrich DataFrame)
                df = self.prepare_import(file_import, df, session)

                # Process the data
                self._process_dataframe(file_import, df, report, session)
                session.commit()

                # Delete file after successful import if enabled
                if self.delete_file_after_import and file_import.status_id == FILE_IMPORT_STATUS_COMPLETED:
                    if file_import.stored_file:
                        stored_file_service.delete_file_sync(file_import.stored_file)
                        logger.info(f"Deleted file after import: {file_import_id}")

            except Exception as ex:
                logger.error(f"Import error for {file_import_id}: {ex}")
                report.add_global_error(REPORT_MESSAGE_NO_FILE, str(ex))
                file_import_service.update_progress(
                    file_import,
                    FILE_IMPORT_STATUS_FAILED,
                    report=report,
                )
                session.commit()
                raise