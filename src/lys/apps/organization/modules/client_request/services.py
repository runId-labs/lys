"""
Services for the client_request module.

`ClientRequestService` owns the lifecycle transitions. Callers state *what happened*
— the request was handled, it failed, it was dropped — rather than assigning a status
and a timestamp by hand, so a request can never end up settled without a settling date,
or in error without a reason.

Sending the request onwards, and deciding whether a failure is worth retrying, belong to
the application that declared the type. This service only records the outcome.
"""
import logging
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.organization.modules.client_request.consts import (
    CLIENT_REQUEST_OPEN_STATUSES,
    CLIENT_REQUEST_REASON_REQUESTER_ANONYMIZED,
    CLIENT_REQUEST_STATUS_CANCELLED,
    CLIENT_REQUEST_STATUS_ERROR,
    CLIENT_REQUEST_STATUS_PROCESSED,
)
from lys.apps.organization.modules.client_request.entities import (
    ClientRequest,
    ClientRequestStatus,
    ClientRequestType,
)
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc

logger = logging.getLogger(__name__)


@register_service()
class ClientRequestTypeService(EntityService[ClientRequestType]):
    """Request types. Values are seeded by the application that acts on them."""


@register_service()
class ClientRequestStatusService(EntityService[ClientRequestStatus]):
    """Request lifecycle statuses."""


@register_service()
class ClientRequestService(EntityService[ClientRequest]):
    """Client requests and their lifecycle."""

    @classmethod
    def mark_processed(
        cls,
        request: ClientRequest,
        reason_code: Optional[str] = None,
    ) -> ClientRequest:
        """Record that the request has been handled and needs nobody else.

        Mutates the instance; the caller owns the transaction.
        """
        request.status_id = CLIENT_REQUEST_STATUS_PROCESSED
        request.reason_code = reason_code
        request.processed_at = now_utc()
        return request

    @classmethod
    def mark_failed(cls, request: ClientRequest, reason_code: str) -> ClientRequest:
        """Record that handling the request failed.

        `processed_at` stays empty on purpose: the request is not settled, it is stuck.
        The reason code is required — a failure nobody can name is a failure nobody can
        act on, and it is what tells a caller whether replaying is worth trying.
        """
        request.status_id = CLIENT_REQUEST_STATUS_ERROR
        request.reason_code = reason_code
        return request

    @classmethod
    def mark_cancelled(cls, request: ClientRequest, reason_code: str) -> ClientRequest:
        """Record that the request will not be handled, and why."""
        request.status_id = CLIENT_REQUEST_STATUS_CANCELLED
        request.reason_code = reason_code
        request.processed_at = now_utc()
        return request

    @classmethod
    async def cancel_open_for_anonymized_user(
        cls, user_id: str, session: AsyncSession
    ) -> int:
        """Settle and scrub the open requests of a user whose account was anonymized.

        Called by the anonymization flow. Two things happen at once, and both matter:

        - the free-text fields are cleared, because a phone number identifies a person
          on its own and a message can name anyone;
        - the requests are cancelled, because nobody is left to serve — and because a
          caller replaying a scrubbed request would send a demand with no requester, no
          contact and no content.

        Settled requests keep their status: the client's history stays readable, and what
        remains on those rows describes a company, not a person.

        Returns the number of requests cancelled.
        """
        statement = (
            update(cls.entity_class)
            .where(
                cls.entity_class.user_id == user_id,
                cls.entity_class.status_id.in_(CLIENT_REQUEST_OPEN_STATUSES),
            )
            .values(
                status_id=CLIENT_REQUEST_STATUS_CANCELLED,
                reason_code=CLIENT_REQUEST_REASON_REQUESTER_ANONYMIZED,
                processed_at=now_utc(),
                contact_phone=None,
                message=None,
            )
            .execution_options(synchronize_session="fetch")
        )
        result = await session.execute(statement)
        cancelled = result.rowcount or 0

        if cancelled:
            logger.info(
                "Cancelled %s open client request(s) for anonymized user %s",
                cancelled, user_id,
            )

        return cancelled

    @classmethod
    async def get_open_for_client(cls, client_id: str, session: AsyncSession) -> list:
        """The requests of one client that still call for an action, oldest first.

        Only open ones: a settled request needs nobody, and a list mixing both stops
        being a signal. The caller gets the rows rather than a count — the count is
        their number, and showing *what* is waiting takes the same query as saying how
        many.
        """
        statement = (
            select(cls.entity_class)
            .where(
                cls.entity_class.client_id == client_id,
                cls.entity_class.status_id.in_(CLIENT_REQUEST_OPEN_STATUSES),
            )
            .order_by(cls.entity_class.created_at)
        )
        result = await session.execute(statement)
        return list(result.scalars().all())

    @classmethod
    async def count_open_by_client(
        cls, client_ids: list[str], session: AsyncSession
    ) -> dict[str, int]:
        """Count the open requests of several clients, in one query.

        Kept for callers that need counts across many clients without their contents —
        a dashboard figure, a batched resolver — where asking per client would cost one
        query per row.
        """
        if not client_ids:
            return {}

        statement = (
            select(cls.entity_class.client_id, func.count(cls.entity_class.id))
            .where(
                cls.entity_class.client_id.in_(client_ids),
                cls.entity_class.status_id.in_(CLIENT_REQUEST_OPEN_STATUSES),
            )
            .group_by(cls.entity_class.client_id)
        )
        result = await session.execute(statement)
        return {client_id: count for client_id, count in result.all()}
