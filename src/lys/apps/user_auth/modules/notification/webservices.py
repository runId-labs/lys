"""
GraphQL webservices for the notification system.

Provides queries and mutations for:
- Listing user notifications
- Getting unread notifications count
- Marking multiple notifications as read in bulk
- Dispatching notification batches (internal service use)
"""
from typing import List, Optional

import strawberry
from sqlalchemy import select, update, Select
from strawberry import relay

from lys.apps.user_auth.modules.notification.nodes import (
    NotificationNode,
    NotificationBatchNode,
    MarkNotificationsReadNode,
    UnreadNotificationsCountNode,
)
from lys.core.consts.webservices import (
    OWNER_ACCESS_LEVEL,
    CONNECTED_ACCESS_LEVEL,
    INTERNAL_SERVICE_ACCESS_LEVEL,
)
from lys.core.contexts import Info
from lys.core.graphql.connection import lys_connection
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation


@strawberry.type
@register_query()
class NotificationQuery(Query):
    """GraphQL queries for notifications."""

    @lys_connection(
        NotificationNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Get all notifications for the current user, ordered by creation date (newest first)."
    )
    async def all_notifications(self, info: Info) -> Select:
        """
        Get all notifications for the authenticated user.

        Returns notifications ordered by creation date (newest first).
        Only returns notifications owned by the current user (OWNER access level).
        """
        notification_entity = info.context.app_manager.get_entity("notification")
        user = info.context.connected_user

        stmt = select(notification_entity).where(
            notification_entity.user_id == user["sub"]
        ).order_by(notification_entity.created_at.desc())

        return stmt

    @lys_field(
        ensure_type=UnreadNotificationsCountNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Get the count of unread notifications for the current user."
    )
    async def unread_notifications_count(self, info: Info) -> UnreadNotificationsCountNode:
        """
        Get the count of unread notifications for the authenticated user.

        Useful for displaying the unread badge on the frontend.

        Returns:
            UnreadNotificationsCountNode with unread_count
        """
        notification_service = info.context.app_manager.get_service("notification")
        user = info.context.connected_user
        session = info.context.session

        unread_count = await notification_service.count_unread(session, user["sub"])

        return UnreadNotificationsCountNode(unread_count=unread_count)


@strawberry.type
@register_mutation()
class NotificationMutation(Mutation):
    """GraphQL mutations for notifications."""

    @lys_field(
        ensure_type=MarkNotificationsReadNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Mark multiple notifications as read in bulk. Returns remaining unread count."
    )
    async def mark_notifications_as_read(
        self,
        info: Info,
        ids: List[relay.GlobalID]
    ) -> MarkNotificationsReadNode:
        """
        Mark multiple notifications as read in a single bulk operation.

        Security is enforced at the database level by filtering on user_id.
        Only notifications belonging to the connected user will be updated.

        Args:
            info: GraphQL context
            ids: List of notification GlobalIDs to mark as read

        Returns:
            MarkNotificationsReadNode with remaining unread_count
        """
        notification_entity = info.context.app_manager.get_entity("notification")
        notification_service = info.context.app_manager.get_service("notification")
        user = info.context.connected_user
        session = info.context.session

        # Extract actual IDs from GlobalIDs
        notification_ids = [gid.node_id for gid in ids]

        # Bulk update with user_id filter for security
        stmt = (
            update(notification_entity)
            .where(
                notification_entity.id.in_(notification_ids),
                notification_entity.user_id == user["sub"]
            )
            .values(is_read=True)
        )

        await session.execute(stmt)

        # Get remaining unread count for badge update
        unread_count = await notification_service.count_unread(session, user["sub"])

        return MarkNotificationsReadNode(unread_count=unread_count)


@strawberry.type
@register_mutation()
class NotificationBatchMutation(Mutation):
    """GraphQL mutations for dispatching notification batches (internal service use)."""

    @lys_field(
        ensure_type=NotificationBatchNode,
        is_public=False,
        access_levels=[INTERNAL_SERVICE_ACCESS_LEVEL],
        is_licenced=False,
        description="Dispatch a notification batch to recipients based on roles and organization scoping. Internal service use only."
    )
    async def dispatch_notification_batch(
        self,
        info: Info,
        type_id: str,
        data: Optional[strawberry.scalars.JSON] = None,
        triggered_by_user_id: Optional[str] = None,
        additional_user_ids: Optional[List[str]] = None,
        organization_data: Optional[strawberry.scalars.JSON] = None,
    ) -> NotificationBatchNode:
        """
        Dispatch a notification batch to all recipients.

        Creates a NotificationBatch and individual Notifications for:
        1. Users with roles linked to the NotificationType (scoped by organization_data)
        2. The user who triggered the notification (if provided)
        3. Any additional user IDs explicitly specified

        Also publishes real-time signals to each recipient's channel.

        Args:
            info: GraphQL context
            type_id: NotificationType ID (e.g., "ORDER_CREATED")
            data: Event data for frontend formatting (JSON)
            triggered_by_user_id: User who triggered the notification (soft FK)
            additional_user_ids: Extra users to notify beyond role-based recipients
            organization_data: Organization scoping (e.g., {"client_ids": ["uuid1", "uuid2"]})

        Returns:
            NotificationBatchNode with created batch information
        """
        session = info.context.session
        service = info.context.app_manager.get_service("notification_batch")

        batch = await service.dispatch(
            session=session,
            type_id=type_id,
            data=data,
            triggered_by_user_id=triggered_by_user_id,
            additional_user_ids=additional_user_ids,
            organization_data=organization_data,
        )

        return NotificationBatchNode.from_entity(batch)