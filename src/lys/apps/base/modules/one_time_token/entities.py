"""
One-time token entities for secure token-based operations.
"""

from datetime import datetime, timedelta

from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship

from lys.apps.base.modules.one_time_token.consts import PENDING_TOKEN_STATUS
from lys.core.entities import Entity, ParametricEntity
from lys.core.registers import register_entity
from lys.core.utils.datetime import now_utc


@register_entity()
class OneTimeTokenStatus(ParametricEntity):
    """
    Status for one-time tokens (pending, used, revoked).
    """
    __tablename__ = "one_time_token_status"


@register_entity()
class OneTimeTokenType(ParametricEntity):
    """
    Type of one-time token (password_reset, email_verification, etc.).
    """
    __tablename__ = "one_time_token_type"

    duration: Mapped[int] = mapped_column(
        nullable=False,
        comment="Token validity duration in minutes"
    )


class OneTimeToken(Entity):
    """
    Base class for one-time use tokens.

    Not registered as entity - should be inherited by specific implementations
    like UserOneTimeToken.

    The entity's id serves as the token (UUID).

    Tokens have:
    - A type (with duration in minutes)
    - A status (pending, used, revoked)
    - created_at is used with type.duration to determine expiration
    """
    __abstract__ = True

    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when token was used"
    )

    status_id: Mapped[str] = mapped_column(
        ForeignKey("one_time_token_status.id"),
        default=PENDING_TOKEN_STATUS
    )

    @declared_attr
    def status(self):
        return relationship("one_time_token_status", lazy='selectin')

    type_id: Mapped[str] = mapped_column(ForeignKey("one_time_token_type.id"))

    @declared_attr
    def type(self):
        return relationship("one_time_token_type", lazy='selectin')

    @property
    def expires_at(self) -> datetime:
        """Calculate token expiration time based on created_at and type duration."""
        from datetime import timezone
        # Ensure created_at has timezone info for comparison
        created = self.created_at
        if created.tzinfo is None:
            # If naive, assume UTC
            created = created.replace(tzinfo=timezone.utc)
        return created + timedelta(minutes=self.type.duration)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return now_utc() >= self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has been used."""
        from lys.apps.base.modules.one_time_token.consts import USED_TOKEN_STATUS
        return self.status_id == USED_TOKEN_STATUS

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (pending status and not expired)."""
        return self.status_id == PENDING_TOKEN_STATUS and not self.is_expired
