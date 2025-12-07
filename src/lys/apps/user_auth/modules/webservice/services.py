from typing import Any, List, Optional

from sqlalchemy import Select, BinaryExpression, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.access_level.entities import AccessLevel
from lys.apps.base.modules.webservice.entities import Webservice
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.apps.user_auth.modules.webservice.entities import WebservicePublicType
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class WebservicePublicTypeService(EntityService[WebservicePublicType]):
    pass

@register_service()
class AuthWebserviceService(WebserviceService):
    @classmethod
    async def _accessible_webservices_or_where(
            cls,
            stmt: Select,
            user: dict[str, Any] | None
    ) -> tuple[Select, Optional[BinaryExpression]]:
        """
        Build access filters for public, connected, and owner access levels.

        This method constructs OR conditions for webservice access based on:
        - Public webservices (public_type_id is not None)
        - Connected user access (CONNECTED_ACCESS_LEVEL)
        - Owner access (OWNER_ACCESS_LEVEL)

        Subclasses should override this method and call super() to add additional
        access level filters (e.g., ROLE_ACCESS_LEVEL, ORGANIZATION_ROLE_ACCESS_LEVEL).

        Args:
            stmt: SQLAlchemy select statement to potentially modify
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Tuple of (statement, where_clause):
            - statement: Potentially modified select statement
            - where_clause: OR conditions for access filtering, or None for super users
        """
        where: Optional[BinaryExpression] = None

        if user is None or user.get("is_super_user", False) is False:
            # Public webservices
            where = cls.entity_class.public_type_id.is_not(None)

            if user is not None:
                access_level_entity: type[AccessLevel] = cls.app_manager.get_entity("access_level")
                # Connected and owner access level webservices
                where |= cls.entity_class.access_levels.any(
                    access_level_entity.id.in_([CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL]),
                    enabled=True
                )

        return stmt, where

    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None
    ) -> Select:
        """
        Get all webservices accessible by a user.

        Builds a query that returns webservices the user can access based on their
        authentication status and access levels. Super users have access to all webservices.

        This method calls _accessible_webservices_or_where() to build the access filters,
        allowing subclasses to extend the filtering logic by overriding that method.

        Args:
            user: Connected user dictionary with id and is_super_user, or None for anonymous

        Returns:
            Select: SQLAlchemy select statement for accessible webservices, ordered by id
        """
        stmt = select(cls.entity_class).distinct()

        stmt, where = await cls._accessible_webservices_or_where(stmt, user)

        if where is not None:
            stmt = stmt.where(where)

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

        Super users get all enabled access levels.
        Regular users get CONNECTED and OWNER access levels if authenticated.

        Args:
            webservice: The Webservice entity
            user: Connected user dictionary with id, or None for anonymous
            session: Database session

        Returns:
            List of AccessLevel entities the user qualifies for
        """
        # Super user gets all enabled access levels
        if user is not None and user.get("is_super_user", False) is True:
            return [al for al in webservice.access_levels if al.enabled]

        qualified = await super().get_user_access_levels(webservice, user, session)

        for access_level in webservice.access_levels:
            if not access_level.enabled:
                continue

            # CONNECTED: user must be authenticated
            if access_level.id == CONNECTED_ACCESS_LEVEL:
                if user is not None:
                    qualified.append(access_level)

            # OWNER: user must be authenticated (actual ownership checked at entity level)
            elif access_level.id == OWNER_ACCESS_LEVEL:
                if user is not None:
                    qualified.append(access_level)

        return qualified