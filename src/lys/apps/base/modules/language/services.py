"""
Services for language management.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.language.consts import FRENCH_LANGUAGE
from lys.apps.base.modules.language.entities import Language
from lys.apps.user_auth.errors import INVALID_LANGUAGE
from lys.core.errors import LysError
from lys.core.registers import register_service
from lys.core.services import EntityService


@register_service()
class LanguageService(EntityService[Language]):
    """
    Service for managing languages.
    """

    @classmethod
    async def get_default_language(cls, session: AsyncSession) -> Language:
        """
        Get the default language (French).

        Args:
            session: Database session

        Returns:
            The default Language entity (French)
        """
        return await cls.get_by_id(FRENCH_LANGUAGE, session)

    @classmethod
    async def get_enabled_languages(cls, session: AsyncSession) -> list[Language]:
        """
        Get all enabled languages.

        Args:
            session: Database session

        Returns:
            List of enabled Language entities
        """
        stmt = select(Language).where(Language.enabled == True).order_by(Language.id.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def validate_language_exists(cls, language_id: str, session: AsyncSession) -> None:
        """
        Validate that a language ID exists in the database.

        Args:
            language_id: The language ID to validate
            session: Database session

        Raises:
            LysError: If language_id doesn't exist in the database
        """
        language = await cls.get_by_id(language_id, session)
        if not language:
            raise LysError(
                INVALID_LANGUAGE,
                f"Language with id '{language_id}' does not exist"
            )
