"""
Role-based recipient resolution mixin.

Extends the base RecipientResolutionMixin with role-based lookup.
Queries the ``user_role`` table to find users whose roles are linked
to the type entity (NotificationType or EmailingType).

Requires ``type_entity`` to have a ``roles`` relationship
(list of Role entities via an association table).
"""
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.base.mixins.recipient_resolution import RecipientResolutionMixin
from lys.core.managers.database import Base

logger = logging.getLogger(__name__)


class RoleRecipientResolutionMixin(RecipientResolutionMixin):
    """
    Extends recipient resolution with role-based lookup.

    Adds resolution of recipients from users with roles linked to the
    type entity via the ``user_role`` table.
    """

    @classmethod
    async def _resolve_recipients(
        cls,
        app_manager,
        session: AsyncSession,
        type_entity,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
    ) -> List[str]:
        """
        Resolve recipient user IDs including role-based recipients.

        Extends base implementation with users whose roles are linked
        to the type entity via the user_role table.

        Args:
            app_manager: Application manager for entity/service lookups
            session: Async database session
            type_entity: Type entity with ``roles`` relationship
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to include

        Returns:
            Deduplicated list of user IDs
        """
        recipient_ids = set(await super()._resolve_recipients(
            app_manager=app_manager,
            session=session,
            type_entity=type_entity,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
        ))

        role_ids = [role.id for role in type_entity.roles]

        if role_ids:
            user_role_entity = app_manager.get_entity("user_role", nullable=True)
            if user_role_entity:
                stmt = select(user_role_entity.user_id).where(
                    user_role_entity.role_id.in_(role_ids)
                )
            else:
                user_role_table = Base.metadata.tables.get("user_role")
                if user_role_table is not None:
                    stmt = select(user_role_table.c.user_id).where(
                        user_role_table.c.role_id.in_(role_ids)
                    )
                else:
                    logger.warning("user_role table not found, skipping role-based recipients")
                    return list(recipient_ids)

            result = await session.execute(stmt)
            for row in result:
                recipient_ids.add(row[0])

        return list(recipient_ids)

    @classmethod
    def _resolve_recipients_sync(
        cls,
        app_manager,
        session: Session,
        type_entity,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
    ) -> List[str]:
        """
        Synchronous version of role-based recipient resolution.

        Args:
            app_manager: Application manager for entity/service lookups
            session: Sync database session
            type_entity: Type entity with ``roles`` relationship
            triggered_by_user_id: User who triggered the event
            additional_user_ids: Extra users to include

        Returns:
            Deduplicated list of user IDs
        """
        recipient_ids = set(super()._resolve_recipients_sync(
            app_manager=app_manager,
            session=session,
            type_entity=type_entity,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
        ))

        role_ids = [role.id for role in type_entity.roles]

        if role_ids:
            user_role_entity = app_manager.get_entity("user_role", nullable=True)
            if user_role_entity:
                stmt = select(user_role_entity.user_id).where(
                    user_role_entity.role_id.in_(role_ids)
                )
            else:
                user_role_table = Base.metadata.tables.get("user_role")
                if user_role_table is not None:
                    stmt = select(user_role_table.c.user_id).where(
                        user_role_table.c.role_id.in_(role_ids)
                    )
                else:
                    logger.warning("user_role table not found, skipping role-based recipients")
                    return list(recipient_ids)

            result = session.execute(stmt)
            for row in result:
                recipient_ids.add(row[0])

        return list(recipient_ids)