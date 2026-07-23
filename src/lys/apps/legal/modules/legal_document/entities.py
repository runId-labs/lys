"""
Entities for the legal_document module.

Three entities:
- `LegalDocumentType` — parametric discriminator (TERMS_OF_USE, SALES_TERMS, …).
- `LegalDocumentVersion` — immutable, append-only registry of published versions.
- `LegalDocumentAcceptance` — append-only consent proof with a self-contained identity
  snapshot that survives anonymization of the user account.
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, Uuid, text,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class LegalDocumentType(ParametricEntity):
    """Document type discriminator (e.g. TERMS_OF_USE, SALES_TERMS, PRIVACY_POLICY).

    A `ParametricEntity` with a business-meaningful string id (the code). The
    `requires_acceptance` flag carries the gating policy on the type itself (server-side
    decision); it is intentionally not exposed by the generic parametric node.
    """
    __tablename__ = "legal_document_type"

    requires_acceptance: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False,
        comment="Whether this type gates access (its current version must be accepted)",
    )


@register_entity()
class LegalDocumentVersion(Entity):
    """Immutable, append-only registry. One row = one published version of one type in
    one language. Rows are never updated or deleted after creation.
    """
    __tablename__ = "legal_document_version"

    type_id: Mapped[str] = mapped_column(
        ForeignKey("legal_document_type.id", ondelete="RESTRICT"),
        nullable=False,
    )

    @declared_attr
    def type(self):
        return relationship("legal_document_type", lazy="selectin")

    language_id: Mapped[str] = mapped_column(
        ForeignKey("language.id", ondelete="RESTRICT"),
        nullable=False,
    )

    @declared_attr
    def language(self):
        return relationship("language", lazy="selectin")

    # Monotonic, human-readable version number per (type_id, language_id).
    version_number: Mapped[int] = mapped_column(nullable=False)

    # SHA-256 of the source Markdown (version identity / idempotency key).
    markdown_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # SHA-256 of the rendered PDF (legal integrity fingerprint), computed by the service.
    pdf_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Object-storage key of the immutable PDF (via the shared storage backend).
    object_key: Mapped[str] = mapped_column(String, nullable=False)

    # When the version takes legal effect (may be >= created_at, supporting a notice period).
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        # Idempotent publication: identical source is never registered twice.
        UniqueConstraint("type_id", "language_id", "markdown_hash",
                         name="uq_legal_version_source"),
        UniqueConstraint("type_id", "language_id", "version_number",
                         name="uq_legal_version_number"),
        # Current-version lookup (greatest effective_date <= now).
        Index("ix_legal_version_current", "type_id", "language_id", "effective_date"),
    )

    # Versions are non-tenant and public: no per-subject row restriction.
    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}


@register_entity()
class LegalDocumentAcceptance(Entity):
    """Append-only consent proof. Records that a subject accepted a specific version at a
    specific time, with a self-contained identity snapshot so the proof does not depend on
    the (mutable, anonymizable) user account.
    """
    __tablename__ = "legal_document_acceptance"

    # FK to the exact version accepted. RESTRICT: versions are append-only, never deleted
    # (both entities live in the legal app, so a real FK is always co-located).
    version_id: Mapped[str] = mapped_column(
        ForeignKey("legal_document_version.id", ondelete="RESTRICT"),
        nullable=False,
    )

    @declared_attr
    def version(self):
        return relationship("legal_document_version", lazy="selectin")

    # Soft FK to the user. Operational link only: nulled when the account is anonymized.
    user_id: Mapped[Optional[str]] = mapped_column(Uuid(as_uuid=False), nullable=True)

    # Identity snapshot at acceptance time — the essential anchor (who accepted).
    accepted_by_email: Mapped[str] = mapped_column(String, nullable=False)

    # Identity snapshot at acceptance time, when available.
    accepted_by_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Corroborating act metadata: ip_address, user_agent, product-specific extras.
    acceptance_context: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Retention clock start. NULL while the relationship is live; set to the user's
    # anonymized_at by the reconciliation job (same update that nulls user_id).
    retention_anchor_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # One acceptance per user per version. NULLs are distinct in SQL, so anonymized
        # rows (user_id nulled) never collide.
        UniqueConstraint("user_id", "version_id", name="uq_legal_acceptance_user_version"),
        Index("ix_legal_acceptance_user", "user_id"),
        Index("ix_legal_acceptance_version", "version_id"),
        Index("ix_legal_acceptance_email", "accepted_by_email"),
        Index("ix_legal_acceptance_retention", "retention_anchor_date"),
    )

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}

    @classmethod
    def user_accessing_filters(cls, stmt, user_id):
        return stmt, [cls.user_id == user_id]
