from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.apps.file_management.modules.file_import.consts import FILE_IMPORT_STATUS_PENDING
from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class FileImportType(ParametricEntity):
    """Import types (e.g., USER_IMPORT, ORGANIZATION_IMPORT, PRODUCT_IMPORT)."""
    __tablename__ = "file_import_type"


@register_entity()
class FileImportStatus(ParametricEntity):
    """Import statuses (e.g., PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED)."""
    __tablename__ = "file_import_status"


@register_entity()
class FileImport(Entity):
    """File import job tracking."""
    __tablename__ = "file_import"

    stored_file_id: Mapped[str] = mapped_column(
        ForeignKey("stored_file.id", ondelete="RESTRICT"),
        nullable=False
    )

    @declared_attr
    def stored_file(self):
        return relationship("stored_file", lazy="selectin")

    type_id: Mapped[str] = mapped_column(
        ForeignKey("file_import_type.id", ondelete="RESTRICT"),
        nullable=False
    )

    @declared_attr
    def type(self):
        return relationship("file_import_type", lazy="selectin")

    status_id: Mapped[str] = mapped_column(
        ForeignKey("file_import_status.id", ondelete="RESTRICT"),
        nullable=False,
        default=FILE_IMPORT_STATUS_PENDING
    )

    @declared_attr
    def status(self):
        return relationship("file_import_status", lazy="selectin")

    # Statistics
    total_rows: Mapped[int] = mapped_column(BigInteger, nullable=True)
    processed_rows: Mapped[int] = mapped_column(BigInteger, nullable=True, default=0)
    success_rows: Mapped[int] = mapped_column(BigInteger, nullable=True, default=0)
    error_rows: Mapped[int] = mapped_column(BigInteger, nullable=True, default=0)

    # Error details: [{"row": 3, "field": "email", "error": "Invalid format", "value": "..."}]
    errors: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Import configuration: {"skip_header": true, "delimiter": ";", "mapping": {...}}
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Additional metadata (user_id, organization_id, etc.)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}