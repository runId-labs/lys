"""
Services for the legal_document module.

- `LegalDocumentTypeService` — CRUD over the parametric type discriminator.
- `LegalDocumentVersionService` — idempotent publication, current-version resolution,
  PDF storage access, and the startup publication hook.
- `LegalDocumentAcceptanceService` — append-only consent proof capture and gate checks.
"""
import asyncio
import hashlib
import ipaddress
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.legal.errors import (
    LEGAL_ACCEPTANCE_EMAIL_REQUIRED,
    LEGAL_PUBLISH_CONTENTION,
    LEGAL_VERSION_NOT_FOUND,
)
from lys.apps.legal.modules.legal_document.consts import (
    DEFAULT_PRESIGNED_URL_EXPIRY,
    FILE_STORAGE_PLUGIN_KEY,
    STORAGE_KEY_PREFIX,
)
from lys.apps.legal.modules.legal_document.entities import (
    LegalDocumentAcceptance,
    LegalDocumentType,
    LegalDocumentVersion,
)
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.pdf import render_markdown_to_pdf_async
from lys.core.utils.storage import StorageBackend, get_configured_storage_backend

logger = logging.getLogger("lys.legal")

# Cap the stored user-agent length (storage/DoS hardening). Note: consumers rendering
# acceptance_context (e.g. an admin UI) MUST escape it — raw UA/IP are attacker-controlled
# and unescaped display is a stored-XSS vector. legal stores; the display layer escapes.
_MAX_USER_AGENT_LENGTH = 512


# Bounded retries for the version-number assignment under concurrent publication.
_PUBLISH_MAX_INSERT_ATTEMPTS = 5


def _anonymize_ip(ip: Optional[str]) -> Optional[str]:
    """Truncate an IP for data minimization (GDPR art. 5.1.c).

    Zeroes the host part (/24 for IPv4, /48 for IPv6), keeping a coarse origin that still
    corroborates the acceptance without retaining a full personal identifier for ~5 years.
    """
    if not ip:
        return None
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False).network_address)


@register_service()
class LegalDocumentTypeService(EntityService[LegalDocumentType]):
    """CRUD over legal document types, plus the gating-set lookup."""

    @classmethod
    async def required_types(cls, session: AsyncSession) -> list[str]:
        """Type codes that gate access: `requires_acceptance` AND `enabled`.

        The gating policy lives on the type (server-side), so this is the single source of
        truth for which types drive the re-consent gate.
        """
        stmt = select(cls.entity_class.id).where(
            cls.entity_class.requires_acceptance.is_(True),
            cls.entity_class.enabled.is_(True),
        )
        return list((await session.execute(stmt)).scalars().all())


@register_service()
class LegalDocumentVersionService(EntityService[LegalDocumentVersion]):
    """Publication, current-version resolution, and PDF storage for legal versions."""

    # ------------------------------------------------------------------ storage

    @classmethod
    def get_storage_backend(cls) -> StorageBackend:
        """Get the shared storage backend instance.

        Uses the same plugin config key as `file_management` so both apps resolve one
        shared backend (memoized in `core/utils/storage`), without coupling to each other.
        """
        return get_configured_storage_backend(cls.app_manager.settings, FILE_STORAGE_PLUGIN_KEY)

    @classmethod
    async def get_presigned_url(
        cls, object_key: str, expires_in: int = DEFAULT_PRESIGNED_URL_EXPIRY
    ) -> str:
        """Return a short-lived presigned URL for a version's stored PDF."""
        return await cls.get_storage_backend().get_presigned_url(object_key, expires_in=expires_in)

    @staticmethod
    def _sha256(data: bytes) -> str:
        """SHA-256 hex digest (mirrors StoredFileService.content_hash for bytes)."""
        return hashlib.sha256(data).hexdigest()

    # --------------------------------------------------------------- resolution

    @classmethod
    async def get_current_version(
        cls, type_id: str, language_id: str, *, session: AsyncSession
    ) -> LegalDocumentVersion:
        """The current version (greatest effective_date <= now) for the exact
        (type, language) pair.

        Strict resolution — no language fallback: raises `LEGAL_VERSION_NOT_FOUND` when no
        version is effective, rather than serving another language (which would make the
        recorded consent legally unsound).
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(cls.entity_class)
            .where(
                cls.entity_class.type_id == type_id,
                cls.entity_class.language_id == language_id,
                cls.entity_class.effective_date <= now,
            )
            .order_by(cls.entity_class.effective_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            raise LysError(
                LEGAL_VERSION_NOT_FOUND,
                f"No effective legal document version for type '{type_id}' "
                f"in language '{language_id}'",
            )
        return version

    # --------------------------------------------------------------- publication

    @classmethod
    async def publish(
        cls,
        type_id: str,
        language_id: str,
        markdown: str,
        *,
        session: AsyncSession,
        effective_date: Optional[datetime] = None,
        template: Optional[str] = None,
        context: Optional[dict] = None,
        base_url: Optional[str] = None,
    ) -> LegalDocumentVersion:
        """Turn an application-owned Markdown source into an immutable version.

        Idempotent: identical source (same markdown_hash) is never published twice — the
        idempotency check short-circuits before any render or upload, which is what
        neutralizes WeasyPrint's non-determinism (render once, freeze).
        """
        markdown_hash = cls._sha256(markdown.encode("utf-8"))

        # Idempotency check — nothing is rendered, uploaded, or written if it exists.
        existing_stmt = select(cls.entity_class).where(
            cls.entity_class.type_id == type_id,
            cls.entity_class.language_id == language_id,
            cls.entity_class.markdown_hash == markdown_hash,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        # Render the PDF exactly once (offloaded to a worker thread: WeasyPrint is sync).
        pdf_bytes = await render_markdown_to_pdf_async(
            markdown, template=template, context=context, base_url=base_url
        )
        pdf_hash = cls._sha256(pdf_bytes)

        # Key embeds the markdown_hash so racing writers target the same immutable object.
        object_key = f"{STORAGE_KEY_PREFIX}/{type_id}/{language_id}/{markdown_hash}.pdf"
        await cls.get_storage_backend().upload(
            object_key, pdf_bytes, content_type="application/pdf"
        )

        # Assign a version number and insert, retrying on a concurrent collision. Two racing
        # writers can collide two ways:
        #   - same source      → unique (type, language, markdown_hash): the loser returns
        #     the winner's row (idempotent);
        #   - different sources → unique (type, language, version_number): the loser
        #     recomputes max+1 and retries.
        # Each attempt re-checks the markdown_hash first (a same-source winner short-circuits)
        # then recomputes the number, inside a SAVEPOINT so the outer transaction survives.
        for _ in range(_PUBLISH_MAX_INSERT_ATTEMPTS):
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing is not None:
                return existing

            max_stmt = select(func.max(cls.entity_class.version_number)).where(
                cls.entity_class.type_id == type_id,
                cls.entity_class.language_id == language_id,
            )
            current_max = (await session.execute(max_stmt)).scalar()
            version_number = (current_max or 0) + 1

            try:
                async with session.begin_nested():
                    version = cls.entity_class(
                        type_id=type_id,
                        language_id=language_id,
                        version_number=version_number,
                        markdown_hash=markdown_hash,
                        pdf_hash=pdf_hash,
                        object_key=object_key,
                        effective_date=effective_date or datetime.now(timezone.utc),
                    )
                    session.add(version)
                return version
            except IntegrityError:
                continue  # a concurrent writer took our hash or number — re-check/retry

        # Retries exhausted under sustained contention: return the winning row if it was a
        # same-source race, else fail loudly (caught+retried next boot by on_initialize).
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing
        raise LysError(
            LEGAL_PUBLISH_CONTENTION,
            f"Could not publish '{type_id}' ({language_id}) after "
            f"{_PUBLISH_MAX_INSERT_ATTEMPTS} attempts (concurrent contention)",
        )

    # ------------------------------------------------------------- startup hook

    @classmethod
    async def on_initialize(cls):
        """Publish declared documents at startup (see settings.legal.documents).

        Iterates the nested `{type: {"languages": {lang: source}}}` shape; each `source` is
        a bare path or an object with per-language publication options.

        Fault-tolerant by contract: `initialize_services` re-raises, which would abort
        startup, so this hook catches and logs its own errors. A failed publication of a
        *new* version never prevents the app from starting nor from serving the existing
        current version; it is retried on the next boot. Each document gets its own session
        so one failure rolls back only that document.
        """
        documents = cls.app_manager.settings.legal.documents
        if not documents:
            return

        for type_id, type_config in documents.items():
            languages = (type_config or {}).get("languages", {})
            for language_id, source in languages.items():
                options = cls._normalize_source(source)
                try:
                    # Offload the blocking file read to a worker thread (consistent with the
                    # PDF render offload) so on_initialize never blocks the event loop at boot.
                    markdown = await asyncio.to_thread(cls._read_markdown, options["path"])
                    async with cls.app_manager.database.get_session() as session:
                        await cls.publish(
                            type_id,
                            language_id,
                            markdown,
                            session=session,
                            effective_date=options.get("effective_date"),
                            template=options.get("template"),
                            context=options.get("context"),
                            base_url=options.get("base_url"),
                        )
                except Exception as exc:
                    logger.error(
                        "Failed to publish legal document '%s' (%s): %s",
                        type_id, language_id, exc,
                    )

    @staticmethod
    def _normalize_source(source) -> dict:
        """Normalize a declared source: a bare path string becomes `{"path": source}`;
        an object is passed through (it must carry a `path`)."""
        if isinstance(source, str):
            return {"path": source}
        return dict(source)

    @staticmethod
    def _read_markdown(path: str) -> str:
        """Read a document's Markdown source from a file path."""
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()


@register_service()
class LegalDocumentAcceptanceService(EntityService[LegalDocumentAcceptance]):
    """Append-only consent proof capture and gate checks.

    `user` is duck-typed (`user.id`, `user.email`, `user.private_data`, `user.language_id`)
    so this service need not import `user_auth`.
    """

    @classmethod
    async def record_acceptance(
        cls, user: Any, version: LegalDocumentVersion, *, session: AsyncSession,
        ip_address: Optional[str] = None, user_agent: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> LegalDocumentAcceptance:
        """Create the append-only proof row with a frozen identity snapshot.

        Corroborating metadata is **minimized here** (service-owned GDPR policy): the IP is
        truncated and the user-agent capped, so every caller — the GraphQL mutation and the
        signup-composition path alike — gets the same minimization, never a full IP.

        Idempotent per (user, version): re-accepting the same version returns the existing
        row rather than inserting a duplicate.
        """
        existing_stmt = select(cls.entity_class).where(
            cls.entity_class.user_id == user.id,
            cls.entity_class.version_id == version.id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        # accepted_by_email is the essential, NOT NULL anchor of the proof ("who accepted").
        # A user with no resolvable email must fail loudly with a domain error, not with an
        # opaque IntegrityError at flush.
        accepted_by_email = cls._snapshot_email(user)
        if not accepted_by_email:
            raise LysError(
                LEGAL_ACCEPTANCE_EMAIL_REQUIRED,
                f"Cannot record acceptance: user '{getattr(user, 'id', '?')}' has no email",
            )

        # Concurrency: a concurrent double-submit can both pass the existence check above.
        # The unique (user_id, version_id) constraint makes one win; wrap the insert in a
        # SAVEPOINT and, on IntegrityError, return the row the winner inserted — preserving
        # the idempotency contract (mirrors publish()).
        try:
            async with session.begin_nested():
                acceptance = cls.entity_class(
                    version_id=version.id,
                    user_id=user.id,
                    accepted_by_email=accepted_by_email,
                    accepted_by_name=cls._snapshot_name(user),
                    acceptance_context=cls._build_acceptance_context(
                        ip_address, user_agent, extra
                    ),
                )
                session.add(acceptance)
            return acceptance
        except IntegrityError:
            return (await session.execute(existing_stmt)).scalar_one()

    @staticmethod
    def _build_acceptance_context(
        ip_address: Optional[str], user_agent: Optional[str], extra: Optional[dict]
    ) -> Optional[dict]:
        """Build the corroborating-metadata dict with data minimization applied."""
        context = dict(extra or {})
        if ip_address:
            context["ip_address"] = _anonymize_ip(ip_address)
        if user_agent:
            context["user_agent"] = user_agent[:_MAX_USER_AGENT_LENGTH]
        return context or None

    @staticmethod
    def _snapshot_email(user: Any) -> Optional[str]:
        """Email snapshot, duck-typed across user models.

        Accepts a plain `user.email` when present; otherwise reads the user_auth model's
        `user.email_address.id` (the email is the PK of the email-address entity). Kept
        attribute-based so `legal` need not import `user_auth`.
        """
        email = getattr(user, "email", None)
        if email:
            return email
        email_address = getattr(user, "email_address", None)
        return email_address.id if email_address is not None else None

    @staticmethod
    def _snapshot_name(user: Any) -> Optional[str]:
        """Best-effort full-name snapshot from user.private_data, when available."""
        private_data = getattr(user, "private_data", None)
        if private_data is None:
            return None
        first = getattr(private_data, "first_name", None) or ""
        last = getattr(private_data, "last_name", None) or ""
        name = f"{first} {last}".strip()
        return name or None

    @classmethod
    async def has_accepted_current(
        cls, user: Any, type_id: str, language_id: str, *, session: AsyncSession
    ) -> bool:
        """Whether the user has an acceptance for the current version of that type."""
        version_service = cls.app_manager.get_service("legal_document_version")
        version = await version_service.get_current_version(
            type_id, language_id, session=session
        )
        stmt = select(cls.entity_class.id).where(
            cls.entity_class.user_id == user.id,
            cls.entity_class.version_id == version.id,
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    @classmethod
    async def outstanding_acceptances(
        cls, user: Any, required_types: Optional[list[str]] = None, *,
        session: AsyncSession,
    ) -> list[str]:
        """Among the gating types, those whose current version — in the user's language —
        the user has not accepted.

        `required_types` defaults to `LegalDocumentTypeService.required_types()` (the types
        flagged `requires_acceptance`); an application may still pass an explicit set.
        """
        if required_types is None:
            type_service = cls.app_manager.get_service("legal_document_type")
            required_types = await type_service.required_types(session)

        outstanding = []
        for type_id in required_types:
            if not await cls.has_accepted_current(
                user, type_id, user.language_id, session=session
            ):
                outstanding.append(type_id)
        return outstanding

    # ------------------------------------------------ retention / anonymization

    @classmethod
    def reconcile_anonymized(
        cls, anonymized_users: list[dict], *, session: Session
    ) -> int:
        """Sever the operational link for newly anonymized users and start the retention
        clock — the single permitted mutation on the append-only proof.

        **Synchronous** (batch-only, run from the Celery reconciliation task via a sync
        session, per the lys Celery convention — never from the async request path).

        For each `{id, anonymized_at}`: set `user_id = NULL` and stamp
        `retention_anchor_date = anonymized_at`, guarded by `user_id IS NOT NULL` so a
        re-processed user is a no-op (idempotent). Evidential content stays frozen. Returns
        the number of proof rows updated.
        """
        updated = 0
        for record in anonymized_users:
            user_id = record.get("id")
            anonymized_at = record.get("anonymized_at")
            if not user_id or not anonymized_at:
                continue
            result = session.execute(
                update(cls.entity_class)
                .where(
                    cls.entity_class.user_id == user_id,
                    cls.entity_class.user_id.isnot(None),
                )
                .values(user_id=None, retention_anchor_date=anonymized_at)
            )
            updated += result.rowcount or 0
        return updated

    @classmethod
    def purge_expired(
        cls, retention_days: int, *, session: Session, now: Optional[datetime] = None
    ) -> int:
        """Delete acceptance rows whose retention has lapsed.

        **Synchronous** (batch-only, run from the Celery purge task via a sync session).

        Selects rows where `retention_anchor_date IS NOT NULL AND retention_anchor_date +
        retention < now`. Anchor is the anonymization date, not `created_at`: a still-active
        customer (anchor NULL) is never purged. Deletes the whole row (snapshot included).
        Returns the number of rows deleted.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=retention_days)
        result = session.execute(
            delete(cls.entity_class).where(
                cls.entity_class.retention_anchor_date.isnot(None),
                cls.entity_class.retention_anchor_date < cutoff,
            )
        )
        return result.rowcount or 0
