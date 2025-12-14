import os
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class StoredFileMimeType(ParametricEntity):
    """MIME types for stored files (e.g., image/png, application/pdf)."""
    __tablename__ = "stored_file_mime_type"


@register_entity()
class StoredFileType(ParametricEntity):
    """Document types for categorization (e.g., USER_IMPORT_FILE, AVATAR, DOCUMENT)."""
    __tablename__ = "stored_file_type"


@register_entity()
class StoredFile(Entity):
    """File metadata stored in database, actual file content is in S3."""
    __tablename__ = "stored_file"

    original_name: Mapped[str] = mapped_column(nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    mime_type_id: Mapped[str] = mapped_column(
        ForeignKey("stored_file_mime_type.id", ondelete="RESTRICT"),
        nullable=False
    )

    @declared_attr
    def mime_type(self):
        return relationship("stored_file_mime_type", lazy="selectin")

    type_id: Mapped[str] = mapped_column(
        ForeignKey("stored_file_type.id", ondelete="RESTRICT"),
        nullable=False
    )

    @declared_attr
    def type(self):
        return relationship("stored_file_type", lazy="selectin")

    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    @property
    def storage_name(self) -> str:
        """Unique filename for S3 storage, preserving original extension."""
        _, ext = os.path.splitext(self.original_name)
        ts = int(self.created_at.timestamp())
        return f"{ts}_{self.id[:8]}{ext}"

    @property
    def path(self) -> str:
        """Full path in S3 bucket: {type_id}/{storage_name}."""
        return f"{self.type_id}/{self.storage_name}"

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}
