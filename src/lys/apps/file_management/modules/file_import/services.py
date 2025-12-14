"""
File import services for processing CSV/Excel imports.
"""
import abc
import logging
from typing import Any, Type, Hashable

from pandas import read_csv, read_excel, DataFrame
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.file_management.modules.file_import.consts import (
    FILE_IMPORT_STATUS_PENDING,
    FILE_IMPORT_STATUS_PROCESSING,
    FILE_IMPORT_STATUS_COMPLETED,
    FILE_IMPORT_STATUS_FAILED,
    REPORT_MESSAGE_WRONG_MIME_TYPE,
    REPORT_MESSAGE_NO_FILE,
    CSV_MIME_TYPE,
    XLS_MIME_TYPE,
    XLSX_MIME_TYPE,
)
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

            # Check MIME type
            mime_type = file_import.stored_file.mime_type_id
            if mime_type not in self.READER_MAPPING:
                report.add_global_error(REPORT_MESSAGE_WRONG_MIME_TYPE, mime_type)
                file_import_service.update_progress(
                    file_import,
                    FILE_IMPORT_STATUS_FAILED,
                    report=report,
                )
                session.commit()
                return

            # Get presigned URL and read file
            try:
                url = stored_file_service.get_presigned_url_sync(file_import.stored_file)

                # Parse config
                config = ImportConfig.from_dict(file_import.config or {})

                # Read file with pandas
                reader = self.READER_MAPPING[mime_type]
                if mime_type == CSV_MIME_TYPE:
                    df = reader(url, delimiter=config.delimiter, encoding=config.encoding)
                else:
                    df = reader(url)

                # Process the data
                self._process_dataframe(file_import, df, report, session)
                session.commit()

            except Exception as ex:
                logger.error(f"Import error for {file_import_id}: {ex}")
                report.add_global_error(REPORT_MESSAGE_NO_FILE, str(ex))
                file_import_service.update_progress(
                    file_import,
                    FILE_IMPORT_STATUS_FAILED,
                    report=report,
                )
                session.commit()