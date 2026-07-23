"""
Celery tasks for the legal app.

Two daily poll jobs acting on `LegalDocumentAcceptance`:
- `legal_reconcile_anonymized_users` — asks user_auth (over GraphQL, as an internal
  service) who was newly anonymized, then severs the operational `user_id` and starts the
  retention clock.
- `legal_purge_expired_acceptances` — deletes proofs whose retention has lapsed.

`legal` provides the callables (mechanism); the consuming service schedules them in its
Celery Beat config. Both are **synchronous** and use `get_sync_session()` — the lys Celery
convention (as in `licensing.tasks` / `StoredFileService._sync`). We deliberately avoid
`asyncio.run()` here: the async engine is cached and would be reused across the fresh event
loops created per task, raising "attached to a different loop".
"""
import base64
import binascii
import logging
import uuid
from datetime import datetime, timedelta, timezone

from celery import current_app, shared_task

from lys.core.graphql.client import GraphQLClient

logger = logging.getLogger("lys.legal")

# Daily cadence + margin: a generous lookback window makes a persisted cursor unnecessary
# (the reconcile UPDATE is idempotent, so overlap re-processing is a no-op).
RECONCILE_LOOKBACK_HOURS = 25

# The producer is a relay connection; the task pages through it (bounded responses).
_ANONYMIZED_USERS_PAGE_SIZE = 100
_ANONYMIZED_USERS_QUERY = """
query AnonymizedUsers($since: DateTime!, $first: Int!, $after: String) {
    anonymizedUsers(since: $since, first: $first, after: $after) {
        edges {
            node {
                id
                anonymizedAt
            }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
"""


def _decode_relay_id(global_id: str) -> str:
    """Decode a Relay global id (base64 of 'TypeName:rawId') to the raw id.

    The feed exposes ids as Relay global ids (framework convention — raw entity ids are
    never sent in clear); the reconciliation UPDATE keys on the raw user id.

    Raises ValueError on any malformed value (bad base64, bad utf-8, missing separator, or
    a non-UUID payload) so the caller can skip that single record without crashing the
    whole reconciliation run.
    """
    try:
        decoded = base64.b64decode(global_id, validate=True).decode()
        raw_id = decoded.split(":", 1)[1]
    except (binascii.Error, UnicodeDecodeError, IndexError) as exc:
        raise ValueError(f"Malformed relay global id: {global_id!r}") from exc
    uuid.UUID(raw_id)  # raises ValueError if not a valid UUID
    return raw_id


@shared_task
def legal_reconcile_anonymized_users() -> int:
    """Reconcile newly anonymized users into the local consent proofs. Returns rows updated."""
    app_manager = current_app.app_manager
    settings = app_manager.settings

    endpoint = settings.legal.anonymized_users_endpoint
    if not endpoint:
        logger.warning(
            "Legal reconciliation skipped: settings.legal.anonymized_users_endpoint is not set"
        )
        return 0

    since = datetime.now(timezone.utc) - timedelta(hours=RECONCILE_LOOKBACK_HOURS)
    anonymized_users = _fetch_anonymized_users(settings, endpoint, since)

    acceptance_service = app_manager.get_service("legal_document_acceptance")
    with app_manager.database.get_sync_session() as session:
        updated = acceptance_service.reconcile_anonymized(anonymized_users, session=session)

    logger.info("Legal reconciliation: %s proof row(s) updated", updated)
    return updated


def _fetch_anonymized_users(settings, endpoint: str, since: datetime) -> list[dict]:
    """Fetch newly anonymized users from user_auth as an internal service (Service JWT).

    Pages through the relay connection until exhausted so a large anonymization batch does
    not overflow a single response.
    """
    client = GraphQLClient(
        url=endpoint,
        secret_key=settings.secret_key,
        service_name="legal",
    )
    users: list[dict] = []
    after = None
    while True:
        # query_sync returns the `data` object directly (and raises on GraphQL errors).
        data = client.query_sync(
            _ANONYMIZED_USERS_QUERY,
            variables={
                "since": since.isoformat(),
                "first": _ANONYMIZED_USERS_PAGE_SIZE,
                "after": after,
            },
        )
        connection = (data or {}).get("anonymizedUsers") or {}
        for edge in connection.get("edges") or []:
            node = edge.get("node") or {}
            # Skip (don't crash on) a single malformed record: one bad id must not abort the
            # whole daily reconciliation, which would leave every retention clock unstarted.
            try:
                raw_id = _decode_relay_id(node["id"])
            except (ValueError, KeyError, TypeError):
                logger.warning("Skipping anonymized user with malformed id: %r", node.get("id"))
                continue
            users.append({"id": raw_id, "anonymized_at": node.get("anonymizedAt")})
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
    return users


@shared_task
def legal_purge_expired_acceptances() -> int:
    """Delete acceptance proofs whose retention has lapsed. Returns rows deleted."""
    app_manager = current_app.app_manager
    retention_days = app_manager.settings.legal.retention_days

    acceptance_service = app_manager.get_service("legal_document_acceptance")
    with app_manager.database.get_sync_session() as session:
        deleted = acceptance_service.purge_expired(retention_days, session=session)

    logger.info("Legal retention purge: %s proof row(s) deleted", deleted)
    return deleted
