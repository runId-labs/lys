from typing import Any, List, Optional

from sqlalchemy import Select, BinaryExpression, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.base.modules.webservice.entities import Webservice
from lys.apps.user_auth.modules.webservice.services import AuthWebserviceService
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.registries import register_service


@register_service()
class RoleWebserviceService(AuthWebserviceService):
    @classmethod
    async def _accessible_webservices_or_where(
            cls,
            stmt: Select,
            user: dict[str, Any] | None
    ) -> tuple[Select, Optional[BinaryExpression]]:
        """
        Build access filters including role-based access.

        Extends parent to add ROLE_ACCESS_LEVEL filter for users with assigned roles.

        Args:
            stmt: SQLAlchemy select statement
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Tuple of (statement, where_clause) with role-based filters added
        """
        stmt, where = await super()._accessible_webservices_or_where(stmt, user)

        # Add role-based access if user is connected and not super user
        if user is not None and user.get("is_super_user", False) is False:
            user_id = user.get("sub")
            if user_id:
                access_level_entity = cls.app_manager.get_entity("access_level")
                role_entity = cls.app_manager.get_entity("role")
                role_webservice_entity = cls.app_manager.get_entity("role_webservice")
                user_entity = cls.app_manager.get_entity("user")

                # Check if webservice is assigned to a role the user has
                role_access_condition = and_(
                    cls.entity_class.access_levels.any(
                        access_level_entity.id == ROLE_ACCESS_LEVEL,
                        enabled=True
                    ),
                    exists(
                        select(role_webservice_entity.id)
                        .join(role_entity, role_webservice_entity.role_id == role_entity.id)
                        .where(
                            role_webservice_entity.webservice_id == cls.entity_class.id,
                            role_entity.users.any(user_entity.id == user_id)
                        )
                    )
                )

                if where is not None:
                    where |= role_access_condition
                else:
                    where = role_access_condition

        return stmt, where

    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None,
            role_code: str | None = None
    ) -> Select:
        """
        Get accessible webservices for a user including role-based access.

        Args:
            user: Connected user dictionary with id, or None for anonymous
            role_code: Optional filter to only return webservices assigned to this role

        Returns:
            Select: SQLAlchemy select statement for accessible webservices
        """
        stmt = await super().accessible_webservices(user)

        # Apply role_code filter on result (filter webservices by role assignment)
        if role_code is not None:
            role_webservice_entity = cls.app_manager.get_entity("role_webservice")
            stmt = stmt.where(
                exists(
                    select(role_webservice_entity.id).where(
                        role_webservice_entity.webservice_id == cls.entity_class.id,
                        role_webservice_entity.role_id == role_code
                    )
                )
            )

        return stmt

    @classmethod
    async def _user_has_role_for_webservice(
            cls,
            user_id: str,
            webservice_id: str,
            session: AsyncSession
    ) -> bool:
        """
        Check if user has a global role that grants access to this webservice.

        Args:
            user_id: The user ID
            webservice_id: The webservice ID
            session: Database session

        Returns:
            True if user has a role that includes this webservice
        """
        role_entity = cls.app_manager.get_entity("role")
        role_webservice_entity = cls.app_manager.get_entity("role_webservice")
        user_entity = cls.app_manager.get_entity("user")

        stmt = (
            select(role_entity)
            .join(role_webservice_entity, role_entity.id == role_webservice_entity.role_id)
            .where(
                role_webservice_entity.webservice_id == webservice_id,
                role_entity.users.any(user_entity.id == user_id)
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

        Adds ROLE access level if the user has a role that grants access.

        Args:
            webservice: The Webservice entity
            user: Connected user dictionary with id, or None for anonymous
            session: Database session

        Returns:
            List of AccessLevel entities the user qualifies for
        """
        qualified = await super().get_user_access_levels(webservice, user, session)

        for access_level in webservice.access_levels:
            if not access_level.enabled:
                continue

            # ROLE: user has a global role that includes this webservice
            if access_level.id == ROLE_ACCESS_LEVEL:
                if user is not None:
                    if await cls._user_has_role_for_webservice(user["sub"], webservice.id, session):
                        qualified.append(access_level)

        return qualified