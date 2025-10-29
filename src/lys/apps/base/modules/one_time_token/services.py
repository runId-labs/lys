"""
Services for one-time token management.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.one_time_token.consts import USED_TOKEN_STATUS, REVOKED_TOKEN_STATUS
from lys.apps.base.modules.one_time_token.entities import (
    OneTimeTokenStatus,
    OneTimeTokenType,
    OneTimeToken
)
from lys.core.registers import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc


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