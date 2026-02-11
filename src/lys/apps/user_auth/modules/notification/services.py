"""
Notification services for user_auth app.

Base services for creating and managing notifications:
- NotificationBatchService: Creates notification batches and dispatches to recipients
- NotificationService: Manages individual user notifications

Recipient resolution is provided by RecipientResolutionMixin (base app) and
extended by user_role (role-based) and organization (org-scoped) mixins.
"""
from typing import List, Callable

# Signal name for real-time notification delivery
NEW_NOTIFICATION_SIGNAL = "NEW_NOTIFICATION"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.base.mixins.recipient_resolution import RecipientResolutionMixin
from lys.apps.user_auth.modules.notification.entities import (
    Notification,
    NotificationBatch,
    NotificationType,
)
from lys.core.registries import register_service
from lys.core.services import EntityService


@register_service()
class NotificationBatchService(RecipientResolutionMixin, EntityService[NotificationBatch]):
    """
    Base service for creating notification batches and dispatching notifications.

    Handles the base flow:
    1. Create a NotificationBatch with event data
    2. Resolve recipients via RecipientResolutionMixin
    3. Create individual Notification for each recipient
    4. Publish signals for real-time delivery

    Recipient resolution is provided by the mixin chain:
    - RecipientResolutionMixin: triggered_by + additional_user_ids
    - RoleRecipientResolutionMixin (user_role app): + role-based
    - OrganizationRecipientResolutionMixin (organization app): + org-scoped
    """

    @classmethod
    async def dispatch(
        cls,
        session: AsyncSession,
        type_id: str,
        data: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> NotificationBatch:
        """
        Create a notification batch and dispatch to all recipients.

        Args:
            session: Database session
            type_id: NotificationType ID (e.g., "ORDER_CREATED")
            data: Event data for frontend formatting
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to notify
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool
                            If None, all recipients receive the notification.

        Returns:
            Created NotificationBatch with associated Notifications

        Raises:
            ValueError: If NotificationType not found
        """
        # Fetch NotificationType
        notification_type = await session.get(
            cls.app_manager.get_entity("notification_type"),
            type_id
        )
        if not notification_type:
            raise ValueError(f"NotificationType '{type_id}' not found")

        # Create the batch
        batch = await cls.create(
            session,
            type_id=type_id,
            triggered_by_user_id=triggered_by_user_id,
            data=data,
        )

        # Resolve recipient user IDs via mixin
        recipient_user_ids = await cls._resolve_recipients(
            app_manager=cls.app_manager,
            session=session,
            type_entity=notification_type,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
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
    async def _create_notifications_and_publish(
        cls,
        session: AsyncSession,
        batch: NotificationBatch,
        recipient_user_ids: List[str],
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> None:
        """
        Create individual notifications and publish real-time signals.

        Args:
            session: Database session
            batch: The NotificationBatch entity
            recipient_user_ids: List of user IDs to notify
            should_send_fn: Optional callback to filter recipients.
                            If provided, only creates notification if returns True.
        """
        notification_service = cls.app_manager.get_service("notification")

        for user_id in recipient_user_ids:
            # Check user preference if callback provided
            if should_send_fn is not None and not should_send_fn(user_id):
                continue

            # Create notification
            await notification_service.create(
                session,
                batch_id=str(batch.id),
                user_id=user_id,
            )

            # Publish signal directly to Redis for real-time delivery
            if cls.app_manager.pubsub:
                await cls.app_manager.pubsub.publish(
                    channel=f"user:{user_id}",
                    signal=NEW_NOTIFICATION_SIGNAL,
                    params={
                        "type_id": batch.type_id,
                        "data": batch.data,
                    }
                )

    @classmethod
    def dispatch_sync(
        cls,
        session: Session,
        type_id: str,
        data: dict | None = None,
        triggered_by_user_id: str | None = None,
        additional_user_ids: List[str] | None = None,
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> NotificationBatch:
        """
        Synchronous version of dispatch for use in Celery tasks.

        Args:
            session: Sync database session
            type_id: NotificationType ID (e.g., "FINANCIAL_IMPORT_COMPLETED")
            data: Event data for frontend formatting
            triggered_by_user_id: User who triggered the notification
            additional_user_ids: Extra users to notify
            should_send_fn: Optional callback to filter recipients by user preference.
                            Signature: (user_id: str) -> bool
                            If None, all recipients receive the notification.

        Returns:
            Created NotificationBatch with associated Notifications

        Raises:
            ValueError: If NotificationType not found
        """
        # Fetch NotificationType
        notification_type = session.get(
            cls.app_manager.get_entity("notification_type"),
            type_id
        )
        if not notification_type:
            raise ValueError(f"NotificationType '{type_id}' not found")

        # Create the batch
        batch = cls.entity_class(
            type_id=type_id,
            triggered_by_user_id=triggered_by_user_id,
            data=data,
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
        )

        # Create individual notifications and publish signals
        cls._create_notifications_and_publish_sync(
            session=session,
            batch=batch,
            recipient_user_ids=recipient_user_ids,
            should_send_fn=should_send_fn,
        )

        return batch

    @classmethod
    def _create_notifications_and_publish_sync(
        cls,
        session: Session,
        batch: NotificationBatch,
        recipient_user_ids: List[str],
        should_send_fn: Callable[[str], bool] | None = None,
    ) -> None:
        """
        Synchronous version of notification creation and signal publishing.

        Args:
            session: Sync database session
            batch: The NotificationBatch entity
            recipient_user_ids: List of user IDs to notify
            should_send_fn: Optional callback to filter recipients.
                            If provided, only creates notification if returns True.
        """
        notification_entity = cls.app_manager.get_entity("notification")

        for user_id in recipient_user_ids:
            # Check user preference if callback provided
            if should_send_fn is not None and not should_send_fn(user_id):
                continue

            # Create notification
            notification = notification_entity(
                batch_id=str(batch.id),
                user_id=user_id,
            )
            session.add(notification)

            # Publish signal to Redis for real-time delivery
            if cls.app_manager.pubsub:
                cls.app_manager.pubsub.publish_sync(
                    channel=f"user:{user_id}",
                    signal=NEW_NOTIFICATION_SIGNAL,
                    params={
                        "type_id": batch.type_id,
                        "data": batch.data,
                    }
                )


@register_service()
class NotificationService(EntityService[Notification]):
    """
    Service for managing individual user notifications.

    Provides operations for:
    - Creating notifications (usually called by NotificationBatchService)
    - Counting unread notifications
    - Querying user notifications
    """

    @classmethod
    async def count_unread(cls, session: AsyncSession, user_id: str) -> int:
        """
        Count unread notifications for a user.

        Used for displaying the unread badge on the frontend.

        Args:
            session: Database session
            user_id: User ID to count unread notifications for

        Returns:
            Number of unread notifications
        """
        stmt = select(func.count()).select_from(cls.entity_class).where(
            cls.entity_class.user_id == user_id,
            cls.entity_class.is_read == False
        )
        result = await session.execute(stmt)
        return result.scalar() or 0


@register_service()
class NotificationTypeService(EntityService[NotificationType]):
    """
    Service for managing notification types.

    Used by fixtures to create and manage NotificationType entities
    with their associated NotificationTypeRole relations.
    """
    pass