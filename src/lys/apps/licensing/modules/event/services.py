"""
Event service extension for licensing app.

Extends the base EventService with licensing-specific events.
"""
from lys.apps.licensing.modules.event import consts
from lys.apps.user_auth.modules.event.services import EventService as BaseEventService
from lys.core.registries import register_service


@register_service()
class EventService(BaseEventService):
    """
    Extended event service with licensing events.

    Inherits user lifecycle events from base EventService and adds
    license-related events.
    """

    @classmethod
    def get_channels(cls) -> dict[str, dict]:
        """
        Extend parent channels with licensing events.

        Returns:
            Dict with base events plus licensing events
        """
        channels = super().get_channels()
        channels.update({
            # License granted: both channels enabled, user can configure
            consts.LICENSE_GRANTED: {
                "email": True,
                "notification": True,
                "blocked": [],
            },
            # License revoked: mandatory (security/compliance)
            consts.LICENSE_REVOKED: {
                "email": True,
                "notification": True,
                "blocked": ["email", "notification"],
            },
            # Subscription payment success: user can configure
            consts.SUBSCRIPTION_PAYMENT_SUCCESS: {
                "email": True,
                "notification": True,
                "blocked": [],
            },
            # Subscription payment failed: mandatory (critical)
            consts.SUBSCRIPTION_PAYMENT_FAILED: {
                "email": True,
                "notification": True,
                "blocked": ["email", "notification"],
            },
            # Subscription canceled: user can configure
            consts.SUBSCRIPTION_CANCELED: {
                "email": True,
                "notification": True,
                "blocked": [],
            },
        })
        return channels