"""
Fixtures for the notification severity table.

Loads the four standard severity levels referenced by NotificationType:
- INFO: neutral or informational notification
- SUCCESS: a successful operation completed
- WARNING: something needs the user's attention but is not blocking
- ERROR: an operation failed and the user should act
"""
from lys.apps.user_auth.modules.notification.consts import (
    NOTIFICATION_SEVERITY_INFO,
    NOTIFICATION_SEVERITY_SUCCESS,
    NOTIFICATION_SEVERITY_WARNING,
    NOTIFICATION_SEVERITY_ERROR,
)
from lys.apps.user_auth.modules.notification.services import NotificationSeverityService
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel
from lys.core.registries import register_fixture


@register_fixture()
class NotificationSeverityFixtures(EntityFixtures[NotificationSeverityService]):
    """
    Fixtures for NotificationSeverity entities.

    Provides the four canonical severity levels used by NotificationType.
    These ids are referenced by NotificationType.severity_id and consumed
    by the frontend to drive the visual rendering of notifications.
    """
    model = ParametricEntityFixturesModel
    delete_previous_data = False

    data_list = [
        {
            "id": NOTIFICATION_SEVERITY_INFO,
            "attributes": {
                "enabled": True,
                "description": "Informational notification. Default severity for neutral events.",
            },
        },
        {
            "id": NOTIFICATION_SEVERITY_SUCCESS,
            "attributes": {
                "enabled": True,
                "description": "Notification reporting a successful operation.",
            },
        },
        {
            "id": NOTIFICATION_SEVERITY_WARNING,
            "attributes": {
                "enabled": True,
                "description": "Notification requiring the user's attention without being blocking.",
            },
        },
        {
            "id": NOTIFICATION_SEVERITY_ERROR,
            "attributes": {
                "enabled": True,
                "description": "Notification reporting a failed operation that the user should investigate.",
            },
        },
    ]