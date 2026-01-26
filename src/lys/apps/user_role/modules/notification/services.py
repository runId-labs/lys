"""
Notification services for user_role app.

Extends base NotificationBatchService with role-based recipient resolution.
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.user_role.modules.notification.entities import NotificationType
from lys.apps.user_auth.modules.notification.services import (
    NotificationBatchService as BaseNotificationBatchService,
)
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class NotificationTypeService(EntityService[NotificationType]):
    """
    Service for managing notification types with roles relationship.

    Uses the extended NotificationType from user_role which includes
    the roles many-to-many relationship.
    """
    pass


@register_service()
class NotificationBatchService(BaseNotificationBatchService):
    """
    Extended NotificationBatchService with role-based recipient resolution.

    Adds resolution of recipients from:
    - Users with roles linked to the NotificationType (via user_role table)
    """

    @classmethod
    async def _resolve_recipients(
        cls,
        session: AsyncSession,
        notification_type: NotificationType,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
    ) -> List[str]:
        """
        Resolve recipient user IDs including role-based recipients.

        Extends base implementation with:
        - Users with roles linked to the NotificationType (via user_role table)

        Args:
            session: Database session
            notification_type: The NotificationType entity
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to include

        Returns:
            Deduplicated list of user IDs
        """
        # Start with base recipients (triggered_by + additional)
        recipient_ids = set(await super()._resolve_recipients(
            session=session,
            notification_type=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
        ))

        # Add role-based recipients
        role_ids = [role.id for role in notification_type.roles]

        if role_ids:
            user_role_entity = cls.app_manager.get_entity("user_role", nullable=True)
            if user_role_entity:
                stmt = select(user_role_entity.user_id).where(
                    user_role_entity.role_id.in_(role_ids)
                )
                result = await session.execute(stmt)
                for row in result:
                    recipient_ids.add(row[0])

        return list(recipient_ids)

    @classmethod
    def _resolve_recipients_sync(
        cls,
        session: Session,
        notification_type: NotificationType,
        triggered_by_user_id: str | None,
        additional_user_ids: List[str] | None,
    ) -> List[str]:
        """
        Synchronous version of role-based recipient resolution.

        Extends base implementation with:
        - Users with roles linked to the NotificationType (via user_role table)
        """
        # Start with base recipients (triggered_by + additional)
        recipient_ids = set(super()._resolve_recipients_sync(
            session=session,
            notification_type=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
        ))

        # Add role-based recipients
        role_ids = [role.id for role in notification_type.roles]

        if role_ids:
            user_role_entity = cls.app_manager.get_entity("user_role", nullable=True)
            if user_role_entity:
                stmt = select(user_role_entity.user_id).where(
                    user_role_entity.role_id.in_(role_ids)
                )
                result = session.execute(stmt)
                for row in result:
                    recipient_ids.add(row[0])

        return list(recipient_ids)