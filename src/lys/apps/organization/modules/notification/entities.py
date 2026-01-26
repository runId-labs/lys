"""
Notification entities extension for organization app.

Extends the base NotificationBatch with organization_data for multi-tenant scoping.
"""
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from lys.apps.user_auth.modules.notification.entities import NotificationBatch as BaseNotificationBatch
from lys.core.registries import register_entity


@register_entity()
class NotificationBatch(BaseNotificationBatch):
    """
    Extended NotificationBatch with organization_data for multi-tenant scoping.

    Overrides the base NotificationBatch from lys.apps.user_auth to add:
    - organization_data: JSON with organization scoping (e.g., client_ids)

    Organization data structure:
        If organization_data is None: use user_role table to resolve recipients
        If organization_data has client_ids: use client_user_role table to resolve recipients
        Example: {"client_ids": ["client-uuid-1", "client-uuid-2"]}

    Attributes:
        organization_data: JSON with organization scoping for multi-tenant filtering
    """

    organization_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Organization scoping data (e.g., client_ids for multi-tenant filtering)"
    )