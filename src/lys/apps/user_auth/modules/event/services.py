"""
Event services for coordinating emails and notifications.

This module provides the base EventService class that defines:
- Event channel configuration (email, notification, blocked)
- User preference management
- Channel resolution logic

The service is designed to be extended by other apps (licensing, eywa.apps.event)
to add their own event types while inheriting the base configuration.

Override chain example:
    lys.apps.user_auth.EventService (base)
    → lys.apps.licensing.EventService (extends base)
    → eywa.apps.event.EventService (extends licensing)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from lys.apps.user_auth.modules.event import consts
from lys.apps.user_auth.modules.event.entities import UserEventPreference
from lys.core.registries import register_service
from lys.core.services import EntityService, Service


@register_service()
class UserEventPreferenceService(EntityService[UserEventPreference]):
    """Service for managing user event preferences (CRUD operations)."""

    @classmethod
    async def create_or_update(
        cls,
        user_id: str,
        event_type: str,
        channel: str,
        enabled: bool,
        session: AsyncSession
    ) -> UserEventPreference:
        """
        Create or update user preference with validation.

        Validates that the channel is not blocked for this event type
        by checking with EventService.

        Args:
            user_id: The user to create preference for
            event_type: The event type key
            channel: The channel type ("email" or "notification")
            enabled: Whether to enable this channel
            session: Async database session

        Returns:
            The created or updated UserEventPreference entity

        Raises:
            ValueError: If event_type is unknown, channel is invalid,
                       or channel is blocked for this event
        """
        # Get event service for validation
        event_service = cls.app_manager.get_service("event")
        channels = event_service.get_channels()
        config = channels.get(event_type)

        if not config:
            raise ValueError(f"Unknown event type: {event_type}")

        if channel not in ("email", "notification"):
            raise ValueError(f"Invalid channel: {channel}")

        if channel in config.get("blocked", []):
            raise ValueError(f"Channel '{channel}' is blocked for event '{event_type}'")

        # Create or update preference
        user_event_preference = cls.app_manager.get_entity("user_event_preference")
        stmt = select(user_event_preference).filter_by(
            user_id=user_id,
            event_type=event_type,
            channel=channel
        )
        result = await session.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref:
            pref.enabled = enabled
        else:
            pref = user_event_preference(
                user_id=user_id,
                event_type=event_type,
                channel=channel,
                enabled=enabled
            )
            session.add(pref)

        return pref

    @classmethod
    async def get_by_user(
        cls,
        user_id: str,
        session: AsyncSession
    ) -> list[UserEventPreference]:
        """
        Get all event preferences for a user.

        Args:
            user_id: The user to get preferences for
            session: Async database session

        Returns:
            List of UserEventPreference entities
        """
        user_event_preference = cls.app_manager.get_entity("user_event_preference")
        stmt = select(user_event_preference).filter_by(user_id=user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())


@register_service()
class EventService(Service):
    """
    Base event service with user lifecycle events.

    Provides channel configuration and user preference management.
    Subclasses should override get_channels() to add their own events.
    """
    service_name = "event"

    @classmethod
    def get_channels(cls) -> dict[str, dict]:
        """
        Return event channels configuration.

        Override in subclass to extend with app-specific events.
        Use super().get_channels() to inherit parent events.

        Returns:
            Dict mapping event types to their channel configuration:
            {
                "EVENT_TYPE": {
                    "email": bool,        # Default: send email?
                    "notification": bool, # Default: send notification?
                    "blocked": list[str], # Channels user cannot modify
                }
            }
        """
        return {
            # User invitation: email mandatory, notification optional
            consts.USER_INVITED: {
                "email": True,
                "notification": False,
                "blocked": ["email"],
            },
            # Email verification: email mandatory
            consts.USER_EMAIL_VERIFICATION_REQUESTED: {
                "email": True,
                "notification": False,
                "blocked": ["email"],
            },
            # Password reset: all blocked (security critical)
            consts.USER_PASSWORD_RESET_REQUESTED: {
                "email": True,
                "notification": False,
                "blocked": ["email", "notification"],
            },
        }

    @classmethod
    def should_send(
        cls,
        user_id: str,
        event_type: str,
        channel: str,
        session: Session
    ) -> bool:
        """
        Check if channel should be sent based on user preference or default.

        Used by trigger_event Celery task.

        Args:
            user_id: The user to check preferences for
            event_type: The event type key
            channel: The channel type ("email" or "notification")
            session: Sync database session

        Returns:
            True if the channel should be sent, False otherwise
        """
        channels = cls.get_channels()
        config = channels.get(event_type)
        if not config:
            return False

        default_value = config.get(channel, False)

        # Query user preference
        user_event_preference = cls.app_manager.get_entity("user_event_preference")
        pref = session.query(user_event_preference).filter_by(
            user_id=user_id,
            event_type=event_type,
            channel=channel
        ).first()

        if pref:
            return pref.enabled
        return default_value

    @classmethod
    def get_user_configurable_events(cls) -> dict[str, dict]:
        """
        Return events that user can configure (not fully blocked).

        Used by frontend to display preference settings.

        Returns:
            Dict of configurable events with their channel info:
            {
                "EVENT_TYPE": {
                    "email": {"default": bool, "configurable": bool},
                    "notification": {"default": bool, "configurable": bool},
                }
            }
        """
        channels = cls.get_channels()
        configurable = {}

        for event_type, config in channels.items():
            blocked = config.get("blocked", [])
            # Event is configurable if at least one channel is not blocked
            if "email" not in blocked or "notification" not in blocked:
                configurable[event_type] = {
                    "email": {
                        "default": config.get("email", False),
                        "configurable": "email" not in blocked,
                    },
                    "notification": {
                        "default": config.get("notification", False),
                        "configurable": "notification" not in blocked,
                    },
                }

        return configurable