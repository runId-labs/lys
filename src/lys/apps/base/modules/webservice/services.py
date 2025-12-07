from typing import Any, List

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.webservice.entities import Webservice
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class WebserviceService(EntityService[Webservice]):
    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None
    ) -> Select[tuple[Webservice]]:
        """
        Get all webservices accessible by a user.

        Base implementation returns all webservices without filtering.
        Subclasses should override this method to add access control logic
        based on user authentication and authorization levels.

        Args:
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Select: SQLAlchemy select statement for accessible webservices, ordered by id
        """
        stmt = select(cls.entity_class).distinct()
        return stmt.order_by(cls.entity_class.id.asc())

    @classmethod
    async def get_user_access_levels(
            cls,
            webservice: Webservice,
            user: dict[str, Any] | None,
            session: AsyncSession
    ) -> List:
        """
        Get the access levels through which the user can access this webservice.

        Base implementation returns an empty list.
        Subclasses should override this method and call super() to add their
        own access level checks.

        Args:
            webservice: The Webservice entity
            user: Connected user dictionary with id, or None for anonymous
            session: Database session

        Returns:
            List of AccessLevel entities the user qualifies for
        """
        return []
