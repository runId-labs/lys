import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.sso.errors import SSO_ACCOUNT_ALREADY_LINKED, SSO_EXTERNAL_ID_CONFLICT
from lys.apps.sso.modules.sso_link.entities import UserSSOLink
from lys.core.errors import LysError
from lys.core.registries import register_service
from lys.core.services import EntityService
from lys.core.utils.datetime import now_utc

logger = logging.getLogger(__name__)


@register_service()
class UserSSOLinkService(EntityService[UserSSOLink]):
    """Service for managing user SSO links."""

    @classmethod
    async def find_by_provider_and_external_id(
        cls,
        provider: str,
        external_user_id: str,
        session: AsyncSession
    ) -> UserSSOLink | None:
        """Find an SSO link by provider and external user ID."""
        stmt = select(cls.entity_class).where(
            cls.entity_class.provider == provider,
            cls.entity_class.external_user_id == external_user_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def find_by_user_and_provider(
        cls,
        user_id: str,
        provider: str,
        session: AsyncSession
    ) -> UserSSOLink | None:
        """Find an SSO link by user ID and provider."""
        stmt = select(cls.entity_class).where(
            cls.entity_class.user_id == user_id,
            cls.entity_class.provider == provider
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def find_all_by_user(
        cls,
        user_id: str,
        session: AsyncSession
    ) -> list[UserSSOLink]:
        """Find all SSO links for a user."""
        stmt = select(cls.entity_class).where(
            cls.entity_class.user_id == user_id
        ).order_by(cls.entity_class.linked_at.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def create_link(
        cls,
        user_id: str,
        provider: str,
        external_user_id: str,
        external_email: str,
        session: AsyncSession
    ) -> UserSSOLink:
        """
        Create a new SSO link between a user and a provider identity.

        Raises:
            LysError: If user already has a link to this provider
            LysError: If the external ID is already linked to another user
        """
        # Check user doesn't already have a link to this provider
        existing_user_link = await cls.find_by_user_and_provider(user_id, provider, session)
        if existing_user_link:
            raise LysError(
                SSO_ACCOUNT_ALREADY_LINKED,
                f"User already has an SSO link for provider '{provider}'"
            )

        # Check external ID isn't already linked to another user
        existing_external_link = await cls.find_by_provider_and_external_id(provider, external_user_id, session)
        if existing_external_link:
            raise LysError(
                SSO_EXTERNAL_ID_CONFLICT,
                f"External ID '{external_user_id}' is already linked to another user for provider '{provider}'"
            )

        link = cls.entity_class(
            user_id=user_id,
            provider=provider,
            external_user_id=external_user_id,
            external_email=external_email,
            linked_at=now_utc()
        )
        session.add(link)
        await session.flush()

        logger.info(f"Created SSO link: user={user_id}, provider={provider}, external_id={external_user_id}")
        return link

    @classmethod
    async def delete_link(
        cls,
        user_id: str,
        provider: str,
        session: AsyncSession
    ) -> bool:
        """
        Delete an SSO link for a user and provider.

        Returns:
            True if a link was deleted, False if no link existed.
        """
        link = await cls.find_by_user_and_provider(user_id, provider, session)
        if not link:
            return False

        await session.delete(link)
        await session.flush()

        logger.info(f"Deleted SSO link: user={user_id}, provider={provider}")
        return True