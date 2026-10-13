"""
Role service for organization app.

Extends RoleService to hide supervisor-only roles from organization members.
"""

from typing import Any

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.user_role.modules.role.services import RoleService
from lys.core.registries import register_service


@register_service()
class OrganizationRoleService(RoleService):
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

        Extends parent: an organization member (client user or client owner) can
        only be given roles that are not supervisor-only, so the others are
        filtered out. The filter is added to the caller's own filters, never
        substituted for them: asking for supervisor-only roles returns nothing.
        Supervisors and super users keep the full list.

        Args:
            session: Database session
            connected_user: JWT claims of the caller, or None
            enabled: When set, keep only roles with this enabled status
            supervisor_only: When set, keep only roles with this supervisor_only flag

        Returns:
            Select: roles ordered by code
        """
        stmt = await super().visible_roles_statement(session, connected_user, enabled, supervisor_only)
        if await cls._is_organization_member(session, connected_user):
            stmt = stmt.where(cls.entity_class.supervisor_only.is_(False))
        return stmt

    @classmethod
    async def _is_organization_member(cls, session: AsyncSession, connected_user: dict[str, Any] | None) -> bool:
        """
        Check whether the caller belongs to an organization or owns one.

        Read from the database rather than the JWT "organizations" claim, which
        is absent for a client user who has no role yet.

        Args:
            session: Database session
            connected_user: JWT claims of the caller, or None

        Returns:
            True if the caller is a client user or a client owner
        """
        if not connected_user or connected_user.get("is_super_user", False):
            return False
        user_id = connected_user.get("sub")
        if not user_id:
            return False

        user_entity = cls.app_manager.get_entity("user")
        client_entity = cls.app_manager.get_entity("client")
        stmt = select(or_(
            exists().where(user_entity.id == user_id, user_entity.client_id.isnot(None)),
            exists().where(client_entity.owner_id == user_id),
        ))
        return bool(await session.scalar(stmt))
