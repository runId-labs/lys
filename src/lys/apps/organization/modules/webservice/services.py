"""
Webservice service for organization app.

Extends RoleWebserviceService to include organization role-based access.
"""

from typing import Any, List, Optional

from sqlalchemy import Select, BinaryExpression, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.webservice.entities import Webservice
from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.modules.webservice.services import RoleWebserviceService
from lys.core.registries import register_service


@register_service()
class OrganizationWebserviceService(RoleWebserviceService):
    @classmethod
    async def _accessible_webservices_or_where(
            cls,
            stmt: Select,
            user: dict[str, Any] | None
    ) -> tuple[Select, Optional[BinaryExpression]]:
        """
        Build access filters including organization role-based access.

        Extends parent to add ORGANIZATION_ROLE_ACCESS_LEVEL filter for users
        with organization roles (client_user_role).

        Args:
            stmt: SQLAlchemy select statement
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Tuple of (statement, where_clause) with organization role filters added
        """
        stmt, where = await super()._accessible_webservices_or_where(stmt, user)

        # Add organization role-based access if user is connected and not super user
        if user is not None and user.get("is_super_user", False) is False:
            user_id = user.get("sub")
            if user_id:
                access_level_entity = cls.app_manager.get_entity("access_level")
                role_entity = cls.app_manager.get_entity("role")
                role_webservice_entity = cls.app_manager.get_entity("role_webservice")
                client_user_role_entity = cls.app_manager.get_entity("client_user_role")
                client_user_entity = cls.app_manager.get_entity("client_user")

                # Webservices with ORGANIZATION_ROLE access level AND user has an org role that grants access
                # Path: webservice -> role_webservice -> role -> client_user_roles -> client_user -> user_id
                org_role_access_condition = and_(
                    cls.entity_class.access_levels.any(
                        access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                        enabled=True
                    ),
                    exists(
                        select(role_webservice_entity.id)
                        .join(role_entity, role_webservice_entity.role_id == role_entity.id)
                        .where(
                            role_webservice_entity.webservice_id == cls.entity_class.id,
                            role_entity.client_user_roles.any(
                                client_user_role_entity.client_user.has(
                                    client_user_entity.user_id == user_id
                                )
                            )
                        )
                    )
                )

                if where is not None:
                    where |= org_role_access_condition
                else:
                    where = org_role_access_condition

        return stmt, where

    @classmethod
    async def _user_has_org_role_for_webservice(
            cls,
            user_id: str,
            webservice_id: str,
            session: AsyncSession
    ) -> bool:
        """
        Check if user has an organization role that grants access to this webservice.

        A user has access if:
        - They are a client owner (owners have access to all ORGANIZATION_ROLE webservices)
        - They have a client_user_role that includes this webservice

        Args:
            user_id: The user ID
            webservice_id: The webservice ID
            session: Database session

        Returns:
            True if user has an organization role that includes this webservice
        """
        # Check if user is a client owner - owners have access to all org role webservices
        client_service = cls.app_manager.get_service("client")
        if await client_service.user_is_client_owner(user_id, session):
            return True

        # Check if user has a client_user_role that grants access
        role_entity = cls.app_manager.get_entity("role")
        role_webservice_entity = cls.app_manager.get_entity("role_webservice")
        client_user_role_entity = cls.app_manager.get_entity("client_user_role")
        client_user_entity = cls.app_manager.get_entity("client_user")

        stmt = (
            select(role_entity)
            .join(role_webservice_entity, role_entity.id == role_webservice_entity.role_id)
            .where(
                role_webservice_entity.webservice_id == webservice_id,
                role_entity.client_user_roles.any(
                    client_user_role_entity.client_user.has(
                        client_user_entity.user_id == user_id
                    )
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @classmethod
    async def get_user_access_levels(
            cls,
            webservice: Webservice,
            user: dict[str, Any] | None,
            session: AsyncSession
    ) -> List:
        """
        Get the access levels through which the user can access this webservice.

        Client owners get all enabled access levels.
        Otherwise, adds ORGANIZATION_ROLE access level if the user has an organization role.

        Args:
            webservice: The Webservice entity
            user: Connected user dictionary with id, or None for anonymous
            session: Database session

        Returns:
            List of AccessLevel entities the user qualifies for
        """
        # Client owner gets all enabled access levels
        if user is not None:
            client_service = cls.app_manager.get_service("client")
            if await client_service.user_is_client_owner(user["sub"], session):
                return [al for al in webservice.access_levels if al.enabled]

        qualified = await super().get_user_access_levels(webservice, user, session)

        for access_level in webservice.access_levels:
            if not access_level.enabled:
                continue

            # ORGANIZATION_ROLE: user has an organization role that includes this webservice
            if access_level.id == ORGANIZATION_ROLE_ACCESS_LEVEL:
                if user is not None:
                    if await cls._user_has_org_role_for_webservice(user["sub"], webservice.id, session):
                        qualified.append(access_level)

        return qualified