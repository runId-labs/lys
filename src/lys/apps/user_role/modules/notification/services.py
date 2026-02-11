"""
Notification services for user_role app.

Extends base NotificationBatchService with role-based recipient resolution
via RoleRecipientResolutionMixin.
"""
from lys.apps.user_role.mixins.recipient_resolution import RoleRecipientResolutionMixin
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
class NotificationBatchService(RoleRecipientResolutionMixin, BaseNotificationBatchService):
    """
    Extended NotificationBatchService with role-based recipient resolution.

    Role-based resolution is provided by RoleRecipientResolutionMixin which
    adds users with roles linked to the NotificationType (via user_role table).

    No method override needed — the mixin's _resolve_recipients() and
    _resolve_recipients_sync() are used automatically via MRO.
    """
    pass