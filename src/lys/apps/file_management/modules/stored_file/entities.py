from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class StoredFileType(ParametricEntity):
    """Document types for categorization (e.g., USER_IMPORT_FILE, AVATAR, DOCUMENT)."""
    __tablename__ = "stored_file_type"


@register_entity()
class StoredFile(Entity):
    """File metadata stored in database, actual file content is in S3."""
    __tablename__ = "stored_file"

    # Client ID (soft reference, no FK - microservices pattern)
    client_id: Mapped[str] = mapped_column(nullable=False)

    original_name: Mapped[str] = mapped_column(nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    mime_type: Mapped[str] = mapped_column(nullable=False)

    type_id: Mapped[str] = mapped_column(
        ForeignKey("stored_file_type.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Full path in S3 bucket (e.g., "DSN_ZIP/2024/12/27/uuid.zip")
    object_key: Mapped[str] = mapped_column(nullable=False)

    @declared_attr
    def type(self):
        return relationship("stored_file_type", lazy="selectin")

    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    @property
    def path(self) -> str:
        """Full path in S3 bucket."""
        return self.object_key

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {
            "client": [self.client_id]
        }

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.client_id.in_(organization_id_dict.get("client", []))]
