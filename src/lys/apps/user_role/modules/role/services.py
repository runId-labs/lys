from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_role.modules.role.entities import Role
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class RoleService(EntityService[Role]):
    @classmethod
    async def visible_roles_statement(
            cls,
            session: AsyncSession,
            connected_user: dict[str, Any] | None,
            enabled: bool | None = None,
            supervisor_only: bool | None = None
    ) -> Select:
        """
        Build the statement listing the roles the connected user may see.

        Every role is visible here; apps that know which callers must not see
        supervisor-only roles narrow the statement by overriding this method.

        Args:
            session: Database session (used by overrides that inspect the caller)
            connected_user: JWT claims of the caller, or None
            enabled: When set, keep only roles with this enabled status
            supervisor_only: When set, keep only roles with this supervisor_only flag

        Returns:
            Select: roles ordered by code
        """
        stmt = select(cls.entity_class).order_by(cls.entity_class.id.asc())
        if enabled is not None:
            stmt = stmt.where(cls.entity_class.enabled == enabled)
        if supervisor_only is not None:
            stmt = stmt.where(cls.entity_class.supervisor_only == supervisor_only)
        return stmt
