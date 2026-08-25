"""
Entities for the client_request module.

Three entities:
- `ClientRequestType` — parametric discriminator, declared by the consuming application.
- `ClientRequestStatus` — parametric lifecycle state (PENDING, PROCESSED, CANCELLED, ERROR).
- `ClientRequest` — one request made by a client, tracked to its outcome.
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime, ForeignKey, Index, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from lys.apps.organization.modules.client_request.consts import (
    CLIENT_REQUEST_STATUS_PENDING,
)
from lys.core.entities import Entity, ParametricEntity
from lys.core.registries import register_entity


@register_entity()
class ClientRequestType(ParametricEntity):
    """What the client is asking for.

    Deliberately empty of values here: lys owns the record, not the catalogue. Each
    application seeds the types it knows how to act on.
    """
    __tablename__ = "client_request_type"


@register_entity()
class ClientRequestStatus(ParametricEntity):
    """Lifecycle state of a request (PENDING, PROCESSED, CANCELLED, ERROR)."""
    __tablename__ = "client_request_status"


@register_entity()
class ClientRequest(Entity):
    """A request made by a client, and what became of it.

    Written before any side effect is attempted. An automation that never receives the
    request, or fails on it, leaves a row in ERROR rather than nothing at all — which is
    the whole point of persisting it here instead of firing and forgetting.

    Retrying is not modelled: whether a failed request is worth replaying, and how often,
    depends on what the consuming application does with it. Some have nothing to retry.
    """
    __tablename__ = "client_request"

    type_id: Mapped[str] = mapped_column(
        ForeignKey("client_request_type.id", ondelete="RESTRICT"),
        nullable=False,
    )

    @declared_attr
    def type(self):
        return relationship("client_request_type", lazy="selectin")

    status_id: Mapped[str] = mapped_column(
        ForeignKey("client_request_status.id", ondelete="RESTRICT"),
        nullable=False,
        default=CLIENT_REQUEST_STATUS_PENDING,
    )

    @declared_attr
    def status(self):
        return relationship("client_request_status", lazy="selectin")

    # The tenant the request belongs to. A request without a client has no meaning.
    client_id: Mapped[str] = mapped_column(
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=False,
    )

    @declared_attr
    def client(self):
        return relationship("client", lazy="selectin")

    # Who asked, when a person did. Null covers the rest: a request opened by an
    # administrator for a client, an import, an automation. Also survives the day an
    # account is hard-deleted rather than anonymized.
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    @declared_attr
    def user(self):
        return relationship("user", lazy="selectin")

    # Contact number for this request, when the requester gave one. Not taken from the
    # account: it is the number to call about *this* demand, which may not be theirs.
    contact_phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # What the client actually wrote. The substance of the demand, and the reason a
    # replay must carry it: rebuilding a request without it changes what was asked.
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Request parameters, owned by the consuming application. lys never reads this.
    # Must not carry personal data: it is kept when the personal fields are cleared.
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Why the request is in its current status. Free-form and application-defined, and
    # only meaningful together with that status: a code on ERROR says what went wrong,
    # the same column on CANCELLED says who dropped it and why.
    reason_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # When the request stopped waiting for anyone. Also the clock a retention rule
    # counts from.
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # The working queue: open requests of one type, oldest first.
        Index("ix_client_request_status_type", "status_id", "type_id"),
        # Per-client counts on a client listing, and a client's own history.
        Index("ix_client_request_client_status", "client_id", "status_id"),
        Index("ix_client_request_user", "user_id"),
        # Age-based retention sweeps.
        Index("ix_client_request_processed", "processed_at"),
    )

    def accessing_users(self) -> list[str]:
        return [self.user_id] if self.user_id else []

    def accessing_organizations(self) -> dict[str, list[str]]:
        return {
            "client": [self.client_id]
        }

    @classmethod
    def user_accessing_filters(cls, stmt, user_id):
        return stmt, [cls.user_id == user_id]

    @classmethod
    def organization_accessing_filters(cls, stmt, organization_id_dict):
        return stmt, [cls.client_id.in_(organization_id_dict.get("client", []))]
