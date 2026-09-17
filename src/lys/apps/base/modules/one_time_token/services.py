"""
Services for one-time token management.
"""
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.base.modules.one_time_token.consts import USED_TOKEN_STATUS, REVOKED_TOKEN_STATUS
from lys.apps.base.modules.one_time_token.entities import (
    OneTimeTokenStatus,
    OneTimeTokenType,
    OneTimeToken
)
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc, ensure_utc


@register_service()
class OneTimeTokenStatusService(EntityService[OneTimeTokenStatus]):
    """
    Service for managing one-time token statuses.
    """
    pass


@register_service()
class OneTimeTokenTypeService(EntityService[OneTimeTokenType]):
    """
    Service for managing one-time token types.
    """
    pass


class OneTimeTokenService:
    """
    Base service for one-time token management.

    Not registered - should be inherited by specific implementations
    like UserOneTimeTokenService.

    Provides common logic for token validation, usage, and revocation.
    """

    @classmethod
    @abstractmethod
    async def get_by_id(cls, entity_id: str, session: AsyncSession):
        raise NotImplementedError

    @classmethod
    async def get_valid_token(cls, token_id: str, session: AsyncSession) -> OneTimeToken | None:
        """
        Get a token only if it's valid (pending status and not expired).

        Args:
            token_id: The token ID (entity id)
            session: Database session

        Returns:
            The token if valid, None otherwise
        """
        token = await cls.get_by_id(token_id, session)

        if token is None:
            return None

        if not token.is_valid:
            return None

        return token

    @classmethod
    async def mark_as_used(cls, token: OneTimeToken, session: AsyncSession) -> None:
        """
        Mark a token as used.

        Args:
            token: The token entity
            session: Database session
        """
        token.status_id = USED_TOKEN_STATUS
        token.used_at = now_utc()
        await session.flush()

    @classmethod
    async def revoke_token(cls, token: OneTimeToken, session: AsyncSession) -> None:
        """
        Revoke a token.

        Args:
            token: The token entity
            session: Database session
        """
        token.status_id = REVOKED_TOKEN_STATUS
        await session.flush()

    @classmethod
    async def use_token(cls, token_id: str, session: AsyncSession) -> OneTimeToken | None:
        """
        Validate and mark a token as used in one operation.

        Args:
            token_id: The token ID (entity id)
            session: Database session

        Returns:
            The token if valid and successfully marked as used, None otherwise
        """
        token = await cls.get_valid_token(token_id, session)

        if token is None:
            return None

        await cls.mark_as_used(token, session)
        return token

    @classmethod
    def purge_expired(
        cls, retention_days: int, *, session: Session, now: Optional[datetime] = None
    ) -> int:
        """Delete one-time tokens whose retention has lapsed (GDPR - 869e7tjpn, 30 days).

        **Synchronous** (run from the Celery purge task via a sync session, same
        convention as lys.apps.legal's purge_expired). Reusable on any OneTimeToken
        subclass mixing this in alongside EntityService, exactly like get_by_id.

        The anchor is `used_at` for a consumed token, else the computed `expires_at`
        (created_at + type.duration - see OneTimeToken.expires_at). Neither is a
        stored column usable in a bulk DELETE ... WHERE - `expires_at` needs the
        type's duration (a join), and portably comparing it needs SQLite as much as
        Postgres (lys's own retention integration tests run on SQLite in-memory, see
        test_legal_retention.py) - so this loads candidates and reuses the entity's
        own `expires_at` property in Python rather than reimplementing the date math
        in SQL. `created_at < cutoff` is a safe coarse pre-filter: `expires_at` and
        `used_at` are never earlier than `created_at`, so nothing eligible for purge
        is excluded by it, only the bulk of long-lived rows that plainly don't
        qualify skip the per-row check below.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=retention_days)

        candidates = session.execute(
            select(cls.entity_class).where(cls.entity_class.created_at < cutoff)
        ).scalars().all()

        expired_ids = [
            token.id for token in candidates
            if ensure_utc(token.used_at or token.expires_at) < cutoff
        ]
        if not expired_ids:
            return 0

        result = session.execute(delete(cls.entity_class).where(cls.entity_class.id.in_(expired_ids)))
        return result.rowcount or 0