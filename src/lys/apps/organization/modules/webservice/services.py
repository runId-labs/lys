"""
Webservice service for organization app.

Extends RoleWebserviceService to include organization role-based access.
"""

from typing import Any

from sqlalchemy import Select, select, and_

from lys.apps.organization.consts import ORGANIZATION_ROLE_ACCESS_LEVEL
from lys.apps.user_role.modules.webservice.services import RoleWebserviceService
from lys.core.registries import register_service


@register_service()
class OrganizationWebserviceService(RoleWebserviceService):
    @classmethod
    async def accessible_webservices(
            cls,
            user: dict[str, Any] | None
    ) -> Select:
        """
        Get accessible webservices for a user including organization role-based access.

        Extends RoleWebserviceService to include webservices accessible via
        client_user_role (organization-level roles).

        Args:
            user: Connected user dictionary with id, or None for anonymous

        Returns:
            Select: SQLAlchemy select statement for accessible webservices
        """
        stmt = select(cls.entity_class).distinct()

        # Get base filters (public, connected, owner, role-based)
        stmt, where = await cls._accessible_webservices_or_where(stmt, user)

        # Add organization role-based access if user is connected and not super user
        if user is not None and user.get("is_super_user", False) is False:
            user_id = user.get("id")
            if user_id:
                # Get entities
                access_level_entity = cls.app_manager.get_entity("access_level")
                role_entity = cls.app_manager.get_entity("role")
                client_user_role_entity = cls.app_manager.get_entity("client_user_role")
                client_user_entity = cls.app_manager.get_entity("client_user")

                # Webservices with ORGANIZATION_ROLE access level AND user has an org role that grants access
                # Path: webservice -> roles -> client_user_roles -> client_user -> user_id
                org_role_access_condition = and_(
                    cls.entity_class.access_levels.any(
                        access_level_entity.id == ORGANIZATION_ROLE_ACCESS_LEVEL,
                        enabled=True
                    ),
                    cls.entity_class.roles.any(
                        role_entity.client_user_roles.any(
                            client_user_role_entity.client_user.has(
                                client_user_entity.user_id == user_id
                            )
                        )
                    )
                )

                # Add to existing where clause
                if where is not None:
                    where |= org_role_access_condition
                else:
                    where = org_role_access_condition

        if where is not None:
            stmt = stmt.where(where)

        return stmt.order_by(cls.entity_class.id.asc())