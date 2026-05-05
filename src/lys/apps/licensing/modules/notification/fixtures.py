"""
Notification type fixtures for licensing app.

Creates NotificationType entries with LICENSE_ADMIN_ROLE association
for licensing notifications.
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lys.apps.licensing.consts import LICENSE_ADMIN_ROLE
from lys.apps.licensing.modules.event.consts import (
    LICENSE_GRANTED,
    LICENSE_REVOKED,
    SUBSCRIPTION_PAYMENT_SUCCESS,
    SUBSCRIPTION_PAYMENT_FAILED,
    SUBSCRIPTION_CANCELED,
)
from lys.apps.licensing.modules.notification.models import NotificationTypeFixturesModel
from lys.apps.user_auth.modules.notification.consts import (
    NOTIFICATION_SEVERITY_SUCCESS,
    NOTIFICATION_SEVERITY_WARNING,
    NOTIFICATION_SEVERITY_ERROR,
)
from lys.apps.user_role.modules.notification.services import NotificationTypeService
from lys.core.fixtures import EntityFixtures
from lys.core.registries import register_fixture


@register_fixture(depends_on=["RoleFixtures", "NotificationSeverityFixtures"])
class NotificationTypeFixtures(EntityFixtures[NotificationTypeService]):
    """
    Fixtures for NotificationType entities.

    Creates notification types with their associated roles and severity.
    """
    model = NotificationTypeFixturesModel
    delete_previous_data = False

    data_list = [
        {
            "id": LICENSE_GRANTED,
            "attributes": {
                "enabled": True,
                "description": "Notification sent to the user when a license is granted.",
                "roles": [],
                "severity_id": NOTIFICATION_SEVERITY_SUCCESS,
            }
        },
        {
            "id": LICENSE_REVOKED,
            "attributes": {
                "enabled": True,
                "description": "Notification sent to the user when a license is revoked.",
                "roles": [],
                "severity_id": NOTIFICATION_SEVERITY_WARNING,
            }
        },
        {
            "id": SUBSCRIPTION_PAYMENT_SUCCESS,
            "attributes": {
                "enabled": True,
                "description": "Notification sent when a subscription payment is successful.",
                "roles": [
                    LICENSE_ADMIN_ROLE,
                ],
                "severity_id": NOTIFICATION_SEVERITY_SUCCESS,
            }
        },
        {
            "id": SUBSCRIPTION_PAYMENT_FAILED,
            "attributes": {
                "enabled": True,
                "description": "Notification sent when a subscription payment fails.",
                "roles": [
                    LICENSE_ADMIN_ROLE,
                ],
                "severity_id": NOTIFICATION_SEVERITY_ERROR,
            }
        },
        {
            "id": SUBSCRIPTION_CANCELED,
            "attributes": {
                "enabled": True,
                "description": "Notification sent when a subscription is canceled.",
                "roles": [
                    LICENSE_ADMIN_ROLE,
                ],
                "severity_id": NOTIFICATION_SEVERITY_WARNING,
            }
        },
    ]

    @classmethod
    async def format_roles(cls, role_ids: List[str], session: AsyncSession) -> List:
        """
        Get Role entities for the given role IDs.

        Args:
            role_ids: List of role ID strings
            session: Database session

        Returns:
            List of Role entities for the many-to-many relationship
        """
        role_class = cls.app_manager.get_entity("role")
        result = await session.execute(
            select(role_class).where(role_class.id.in_(role_ids))
        )
        return list(result.scalars().all())