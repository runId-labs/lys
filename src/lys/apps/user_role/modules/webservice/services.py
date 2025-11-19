from typing import Any

from sqlalchemy import Select, select, and_

from lys.apps.user_auth.modules.webservice.services import AuthWebserviceService
from lys.apps.user_role.consts import ROLE_ACCESS_LEVEL
from lys.core.registers import register_service


@register_service()
class RoleWebserviceService(AuthWebserviceService):
    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None
    ) -> Select:
        """
        Get accessible webservices for a user including role-based access.

        Extends base implementation to include webservices accessible via user roles.

        Args:
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Select: SQLAlchemy select statement for accessible webservices
        """
        stmt = select(cls.entity_class).distinct()

        # Get base filters (public, connected, owner)
        stmt, where = await cls._accessible_webservices_or_where(stmt, user)

        # Add role-based access if user is connected and not super user
        if user is not None and user.get("is_super_user", False) is False:
            user_id = user.get("id")
            if user_id:
                # Get entities
                access_level_entity = cls.app_manager.get_entity("access_level")
                role_entity = cls.app_manager.get_entity("role")
                user_entity = cls.app_manager.get_entity("user")

                # Webservices with ROLE access level AND user has a role that grants access
                role_access_condition = and_(
                    cls.entity_class.access_levels.any(
                        access_level_entity.id == ROLE_ACCESS_LEVEL,
                        enabled=True
                    ),
                    cls.entity_class.roles.any(
                        role_entity.users.any(user_entity.id == user_id)
                    )
                )

                # Add to existing where clause
                if where is not None:
                    where |= role_access_condition
                else:
                    where = role_access_condition

        if where is not None:
            stmt = stmt.where(where)

        return stmt.order_by(cls.entity_class.id.asc())