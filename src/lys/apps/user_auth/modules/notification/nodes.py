"""
GraphQL nodes for the notification system.

Provides GraphQL types for:
- NotificationSeverityNode: Severity level of a notification (info/success/warning/error)
- NotificationTypeNode: Notification type with link to its severity
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

from lys.apps.user_auth.modules.notification.entities import Notification, NotificationBatch, NotificationType
from lys.apps.user_auth.modules.notification.services import (
    NotificationService,
    NotificationBatchService,
    NotificationTypeService,
    NotificationSeverityService,
)
from lys.core.graphql.nodes import EntityNode, ServiceNode, parametric_node
from lys.core.registries import register_node
from lys.core.services import Service


@register_node()
@parametric_node(NotificationSeverityService)
class NotificationSeverityNode:
    """
    GraphQL node representing the severity level of a notification.

    Drives the visual rendering of notifications on the frontend
    (icon + colour). Standard codes: INFO, SUCCESS, WARNING, ERROR.

    The `@parametric_node` decorator wires the standard parametric fields
    (id Relay GlobalID, code, enabled, description, timestamps).
    """
    pass


@register_node()
class NotificationTypeNode(EntityNode[NotificationTypeService], relay.Node):
    """
    GraphQL node representing a notification type.

    Each type carries a severity (foreign key) used by the frontend
    to render the notification with the correct visual cue.

    Cannot use `@parametric_node` directly because we add custom fields
    (`severity_id` scalar + `severity` relation). Instead we declare
    `code: str` manually, which Strawberry maps to the inherited
    `ParametricEntity.code` property at resolve time.
    """
    id: relay.NodeID[str]
    code: str
    created_at: datetime
    updated_at: Optional[datetime]
    severity_id: str
    _entity: strawberry.Private[NotificationType]

    @strawberry.field(description="The severity level of this notification type")
    async def severity(self, info: Info) -> NotificationSeverityNode:
        """
        Get the severity level of this notification type.

        Args:
            info: GraphQL context containing the database session

        Returns:
            NotificationSeverityNode: The severity node
        """
        return await self._lazy_load_relation('severity', NotificationSeverityNode, info)


@register_node()
class NotificationBatchNode(EntityNode[NotificationBatchService], relay.Node):
    """
    GraphQL node representing a notification batch.

    A batch groups all notifications sent for a single event.
    Contains the notification type (with severity) and event data
    for frontend formatting. Consumers read `type.id` to identify
    the notification kind and `type.severity.id` for the visual cue.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    data: Optional[strawberry.scalars.JSON]
    _entity: strawberry.Private[NotificationBatch]

    @strawberry.field(description="The notification type, with its severity")
    async def type(self, info: Info) -> NotificationTypeNode:
        """
        Get the notification type for this batch.

        The type carries the severity used by the frontend
        to render the notification with the correct visual cue.

        Args:
            info: GraphQL context containing the database session

        Returns:
            NotificationTypeNode: The notification type node
        """
        return await self._lazy_load_relation('type', NotificationTypeNode, info)


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