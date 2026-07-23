"""
Webservices for the legal_document module.

- GraphQL queries/mutations: read the current version, list outstanding acceptances,
  record consent.
- Public REST routes: stable, permanently-linkable PDF URLs (before authentication),
  wired like the Mollie webhook (module-level `router`, auto-mounted by lys).
"""
import logging

import strawberry
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from strawberry import relay

from lys.apps.legal.errors import (
    LEGAL_AUTHENTICATION_REQUIRED,
    LEGAL_STORAGE_ERROR,
    LEGAL_VERSION_ID_NOT_FOUND,
)
from lys.apps.legal.modules.legal_document.consts import (
    DEFAULT_PRESIGNED_URL_EXPIRY,
    LEGAL_ROUTE_PREFIX,
)
from lys.apps.legal.modules.legal_document.nodes import (
    LegalDocumentAcceptanceNode,
    LegalDocumentVersionNode,
    OutstandingLegalAcceptancesNode,
)
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.errors import LysError
from lys.core.graphql.create import lys_creation
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_mutation, register_query
from lys.core.graphql.types import Mutation, Query
from lys.core.managers.app import LysAppManager
from lys.core.utils.storage import StorageError
from lys.core.utils.validators import validate_uuid

logger = logging.getLogger("lys.legal")


# =============================================================================
# GraphQL
# =============================================================================

@register_query()
@strawberry.type
class LegalDocumentQuery(Query):
    """GraphQL queries for legal documents."""

    @lys_field(
        ensure_type=LegalDocumentVersionNode,
        is_public=True,
        is_licenced=False,
        description="Read the current legal document version for a (type, language). "
                    "Public: terms must be readable before acceptance / at signup.",
    )
    async def current_legal_document(
        self, info: Info, type_id: str, language_id: str
    ) -> LegalDocumentVersionNode:
        version_service = info.context.app_manager.get_service("legal_document_version")
        version = await version_service.get_current_version(
            type_id, language_id, session=info.context.session
        )
        return LegalDocumentVersionNode.from_obj(version)

    @lys_field(
        ensure_type=OutstandingLegalAcceptancesNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Type codes the connected user still owes acceptance for "
                    "(drives the re-consent gate).",
    )
    async def outstanding_legal_acceptances(self, info: Info) -> OutstandingLegalAcceptancesNode:
        connected_user = info.context.connected_user
        if not connected_user:
            raise LysError(LEGAL_AUTHENTICATION_REQUIRED, "Authentication required")

        app_manager = info.context.app_manager
        session = info.context.session
        user = await app_manager.get_service("user").get_by_id(connected_user["sub"], session)

        # required_types defaults to the gating types (LegalDocumentType.requires_acceptance).
        acceptance_service = app_manager.get_service("legal_document_acceptance")
        type_ids = await acceptance_service.outstanding_acceptances(user, session=session)
        return OutstandingLegalAcceptancesNode(type_ids=type_ids)


@register_mutation()
@strawberry.type
class LegalDocumentMutation(Mutation):
    """GraphQL mutations for legal documents."""

    @lys_creation(
        ensure_type=LegalDocumentAcceptanceNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Record the connected user's consent for the specific version shown.",
    )
    async def accept_legal_document(self, info: Info, version_id: relay.GlobalID):
        """Create the consent proof for the connected user and the shown version.

        Returns the acceptance entity; lys_creation persists it, re-checks access, and wraps
        it in the node. Idempotent per (user, version) at the service level.
        """
        connected_user = info.context.connected_user
        if not connected_user:
            raise LysError(LEGAL_AUTHENTICATION_REQUIRED, "Authentication required")

        app_manager = info.context.app_manager
        session = info.context.session

        user = await app_manager.get_service("user").get_by_id(connected_user["sub"], session)

        version_service = app_manager.get_service("legal_document_version")
        version = await version_service.get_by_id(version_id.node_id, session)
        if version is None:
            raise LysError(
                LEGAL_VERSION_ID_NOT_FOUND,
                f"Legal document version '{version_id.node_id}' not found",
            )

        acceptance_service = app_manager.get_service("legal_document_acceptance")
        return await acceptance_service.record_acceptance(
            user, version, session=session,
            ip_address=info.context.client_ip, user_agent=info.context.user_agent,
        )


# =============================================================================
# Public REST PDF routes
# =============================================================================

router = APIRouter(prefix=f"/{LEGAL_ROUTE_PREFIX}", tags=["legal"])


def _get_app_manager() -> LysAppManager:
    return LysAppManager()


async def _presigned_url(version_service, object_key: str) -> str:
    """Presign a version's stored PDF, converting a storage misconfiguration into a clean
    domain error instead of a raw `StorageError` on a public endpoint.

    Presigning is offline (no S3 round-trip), so this only fails on config/credentials — a
    real storage outage surfaces downstream when the client follows the redirect, not here.
    Hence a 500 (misconfiguration), not a 503 (transient outage).
    """
    try:
        return await version_service.get_presigned_url(
            object_key, expires_in=DEFAULT_PRESIGNED_URL_EXPIRY
        )
    except StorageError as exc:
        raise LysError(LEGAL_STORAGE_ERROR, f"Failed to presign legal PDF: {exc}") from exc


# NOTE: route order matters — FastAPI matches in declaration order. The specific
# `/versions/{version_id}` MUST be declared before the generic `/{type_id}/{language_id}`,
# otherwise `/legal/versions/abc` would match the generic route (type_id="versions").
@router.get("/versions/{version_id}")
async def legal_version_pdf(version_id: str):
    """Redirect to a specific immutable version's PDF. Public, unauthenticated.

    Intentionally serves ANY version by id — including a future-effective one — with no
    `effective_date` gate. This is by design: a version's PDF must be permanently linkable
    (proof retrieval, DSAR), and ids are unguessable `uuid4` never surfaced before the
    version is effective, so pre-embargo confidentiality is not relied upon here.
    """
    # Validate the id shape before querying: a non-UUID value would hit the Uuid column and
    # raise a backend syntax error (500 + stack leak) instead of a clean 404.
    validate_uuid(version_id, LEGAL_VERSION_ID_NOT_FOUND)

    app_manager = _get_app_manager()
    version_service = app_manager.get_service("legal_document_version")
    async with app_manager.database.get_session() as session:
        version = await version_service.get_by_id(version_id, session)
        if version is None:
            raise LysError(
                LEGAL_VERSION_ID_NOT_FOUND,
                f"Legal document version '{version_id}' not found",
            )
        url = await _presigned_url(version_service, version.object_key)
    # Audit the resource served (not the requester IP — that would put PII in app logs).
    logger.info("Legal PDF served: version=%s", version_id)
    return RedirectResponse(url, status_code=302)


@router.get("/{type_id}/{language_id}")
async def current_legal_pdf(type_id: str, language_id: str):
    """Redirect to the current version's PDF for a (type, language). Public, unauthenticated.

    Missing language raises `LEGAL_VERSION_NOT_FOUND` (HTTP 404) — a publication gap, never
    a language fallback.
    """
    app_manager = _get_app_manager()
    version_service = app_manager.get_service("legal_document_version")
    async with app_manager.database.get_session() as session:
        version = await version_service.get_current_version(type_id, language_id, session=session)
        url = await _presigned_url(version_service, version.object_key)
    logger.info("Legal PDF served: type=%s language=%s version=%s", type_id, language_id, version.id)
    return RedirectResponse(url, status_code=302)
