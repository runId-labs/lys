"""
GraphQL nodes for the notification system.

Provides GraphQL types for:
- NotificationBatchNode: Batch of notifications for an event (contains type and data)
- NotificationNode: Individual user notification with navigation to batch
- UnreadNotificationsCountNode: Unread count for badge display
- MarkNotificationsReadNode: Result of bulk mark as read operation
"""
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import relay
from strawberry.types import Info

from lys.apps.user_auth.modules.notification.entities import Notification
from lys.apps.user_auth.modules.notification.services import (
    NotificationService,
    NotificationBatchService,
)
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node
from lys.core.services import Service


@register_node()
class NotificationBatchNode(EntityNode[NotificationBatchService], relay.Node):
    """
    GraphQL node representing a notification batch.

    A batch groups all notifications sent for a single event.
    Contains the notification type and event data for frontend formatting.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    type_id: str
    data: Optional[strawberry.scalars.JSON]


@register_node()
class NotificationNode(EntityNode[NotificationService], relay.Node):
    """
    GraphQL node representing an individual user notification.

    Each notification belongs to a batch and tracks read status
    independently for each recipient. Provides navigation to parent batch.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    user_id: str
    is_read: bool
    _entity: strawberry.Private[Notification]

    @strawberry.field(description="The notification batch containing type and data")
    async def batch(self, info: Info) -> NotificationBatchNode:
        """
        Get the parent notification batch.

        The batch contains the notification type and event data
        used by the frontend for formatting.

        Args:
            info: GraphQL context containing the database session

        Returns:
            NotificationBatchNode: The parent batch node
        """
        return await self._lazy_load_relation('batch', NotificationBatchNode, info)


@register_node()
class UnreadNotificationsCountNode(ServiceNode[Service]):
    """
    Node for unread notifications count query.

    Returns the count of unread notifications for the user,
    useful for displaying the unread badge on the frontend.
    """
    unread_count: int


@register_node()
class MarkNotificationsReadNode(ServiceNode[Service]):
    """
    Result node for bulk mark notifications as read operation.

    Returns the count of remaining unread notifications for the user,
    useful for updating the unread badge on the frontend.
    """
    unread_count: int