from typing import Any, List

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.webservice.entities import Webservice
from lys.core.models.webservices import WebserviceFixturesModel
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

    @classmethod
    async def register_webservices(
            cls,
            webservices: List[WebserviceFixturesModel],
            session: AsyncSession
    ) -> int:
        """
        Register webservices from a business microservice.

        This method upserts webservices into the database. Called by business
        microservices at startup to register their webservices with Auth Server.

        Args:
            webservices: List of webservice configurations to register
            session: Database session

        Returns:
            Number of webservices registered
        """
        access_level_entity = cls.app_manager.get_entity("access_level")

        for ws_config in webservices:
            # Fetch access levels first
            access_levels = []
            for access_level_id in ws_config.attributes.access_levels:
                access_level = await session.get(access_level_entity, access_level_id)
                if access_level:
                    access_levels.append(access_level)

            # Check if webservice exists
            webservice = await session.get(cls.entity_class, ws_config.id)

            if webservice is None:
                # Create with all attributes
                webservice = cls.entity_class(
                    id=ws_config.id,
                    public_type_id=ws_config.attributes.public_type,
                    is_licenced=ws_config.attributes.is_licenced,
                    enabled=ws_config.attributes.enabled,
                    access_levels=access_levels
                )
                session.add(webservice)
            else:
                # Update existing
                webservice.public_type_id = ws_config.attributes.public_type
                webservice.is_licenced = ws_config.attributes.is_licenced
                webservice.enabled = ws_config.attributes.enabled
                webservice.access_levels = access_levels

        await session.flush()
        return len(webservices)
