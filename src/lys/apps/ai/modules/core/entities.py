"""
AI prompt version entity.

One row = one version of one prompt for one purpose. Rows are immutable after
creation and never updated or deleted: the hash carries identity, so identical
content is never registered twice.

`purpose` is the same vocabulary as `AIConversation.purpose` and the endpoint
keys in `AIConfig.endpoints` (e.g. "chatbot", "text_improvement"). The routes
manifest is versioned as a whole document under the dedicated
`ROUTES_MANIFEST_PURPOSE` (see `AIService`).
"""
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lys.core.entities import Entity
from lys.core.registries import register_entity


@register_entity()
class AIPromptVersion(Entity):
    """Immutable, append-only registry of AI prompt versions.

    Populated at boot by ``AIService.on_initialize`` from two sources: the
    configured endpoints' system prompts, and the routes manifest (registered
    with its hash as a single document — page prompts are part of it).
    A concurrent boot race is handled with ``begin_nested()`` + ``IntegrityError``
    (same pattern as ``LegalDocumentVersionService.publish``).
    """

    __tablename__ = "ai_prompt_version"

    purpose: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("purpose", "hash", name="uq_ai_prompt_version_purpose_hash"),
    )

    def accessing_users(self) -> list[str]:
        return []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {}
