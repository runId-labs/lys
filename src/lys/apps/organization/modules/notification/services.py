"""
Notification services for organization app.

Extends NotificationBatchService with organization-scoped recipient resolution
via OrganizationRecipientResolutionMixin.
Inherits role-based resolution from user_role app.
"""
from typing import List, Callable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.organization.mixins.recipient_resolution import OrganizationRecipientResolutionMixin
from lys.apps.organization.modules.notification.entities import NotificationBatch
from lys.apps.user_role.modules.notification.services import (
    NotificationBatchService as BaseNotificationBatchService,
)
from lys.core.registries import register_service


@register_service()
class NotificationBatchService(OrganizationRecipientResolutionMixin, BaseNotificationBatchService):
    """
    Extended NotificationBatchService with organization-scoped recipient resolution.

    Inherits from user_role.NotificationBatchService which provides role-based resolution.

    Adds:
    - organization_data parameter for multi-tenant scoping
    - Resolution of recipients from client_user_role table based on organization levels

    Organization data validation and recipient resolution are provided by
    OrganizationRecipientResolutionMixin.
    """

    @classmethod
    async def dispatch(
        cls,
        session: AsyncSession,
        type_id: str,
        data: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        organization_data: dict | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> NotificationBatch:
        """
        Create a notification batch and dispatch to all recipients.

        Extended implementation adds organization_data for multi-tenant scoping.

        Args:
            session: Database session
            type_id: NotificationType ID (e.g., "ORDER_CREATED")
            data: Event data for frontend formatting
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to notify
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool
                            If None, all recipients receive the notification.

        Returns:
            Created NotificationBatch with associated Notifications

        Raises:
            ValueError: If NotificationType not found
            pydantic.ValidationError: If organization_data is invalid
        """
        # Validate organization_data
        validated_org_data = cls.validate_organization_data(organization_data)

        # Fetch NotificationType
        notification_type = await session.get(
            cls.app_manager.get_entity("notification_type"),
            type_id
        )
        if not notification_type:
            raise ValueError(f"NotificationType '{type_id}' not found")

        # Create the batch with organization_data
        batch = await cls.create(
            session,
            type_id=type_id,
            triggered_by_user_id=triggered_by_user_id,
            data=data,
            organization_data=organization_data,
        )

        # Resolve recipient user IDs via mixin
        recipient_user_ids = await cls._resolve_recipients(
            app_manager=cls.app_manager,
            session=session,
            type_entity=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=validated_org_data,
        )

        # Create individual notifications and publish signals
        await cls._create_notifications_and_publish(
            session=session,
            batch=batch,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

        return batch

    @classmethod
    def dispatch_sync(
        cls,
        session: Session,
        type_id: str,
        data: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        organization_data: dict | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> NotificationBatch:
        """
        Synchronous version of dispatch for use in Celery tasks.

        Extended implementation adds organization_data for multi-tenant scoping.

        Args:
            session: Sync database session
            type_id: NotificationType ID (e.g., "FINANCIAL_IMPORT_COMPLETED")
            data: Event data for frontend formatting
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to notify
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool
                            If None, all recipients receive the notification.
        """
        # Validate organization_data
        validated_org_data = cls.validate_organization_data(organization_data)

        # Fetch NotificationType
        notification_type = session.get(
            cls.app_manager.get_entity("notification_type"),
            type_id
        )
        if not notification_type:
            raise ValueError(f"NotificationType '{type_id}' not found")

        # Create the batch with organization_data
        batch = cls.entity_class(
            type_id=type_id,
            triggered_by_user_id=triggered_by_user_id,
            data=data,
            organization_data=organization_data,
        )
        session.add(batch)
        session.flush()

        # Resolve recipient user IDs via mixin
        recipient_user_ids = cls._resolve_recipients_sync(
            app_manager=cls.app_manager,
            session=session,
            type_entity=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=validated_org_data,
        )

        # Create individual notifications and publish signals
        cls._create_notifications_and_publish_sync(
            session=session,
            batch=batch,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

        return batch