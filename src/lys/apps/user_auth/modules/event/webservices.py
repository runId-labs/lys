"""
GraphQL webservices for the event system.

Provides queries and mutations for:
- Getting configurable events (for preferences page)
- Getting user event preferences
- Creating/updating user event preferences
"""
import strawberry

from lys.apps.user_auth.modules.event.inputs import SetEventPreferenceInput
from lys.apps.user_auth.modules.event.nodes import (
    UserEventPreferenceNode,
    ConfigurableEventNode,
    ConfigurableEventChannelNode,
    ConfigurableEventsNode,
    UserEventPreferencesNode,
)
from lys.core.consts.webservices import CONNECTED_ACCESS_LEVEL, OWNER_ACCESS_LEVEL
from lys.core.contexts import Info
from lys.core.graphql.create import lys_creation
from lys.core.graphql.fields import lys_field
from lys.core.graphql.registries import register_query, register_mutation
from lys.core.graphql.types import Query, Mutation


@strawberry.type
@register_query()
class EventQuery(Query):
    """GraphQL queries for event configuration."""

    @lys_field(
        ensure_type=ConfigurableEventsNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Get all configurable events for the preferences page."
    )
    async def configurable_events(self, info: Info) -> ConfigurableEventsNode:
        """
        Get all events that the user can configure.

        Returns events where at least one channel is not blocked,
        with information about default values and configurability.
        """
        event_service = info.context.app_manager.get_service("event")
        configurable = event_service.get_user_configurable_events()

        events = []
        for event_type, config in configurable.items():
            events.append(ConfigurableEventNode(
                event_type=event_type,
                email=ConfigurableEventChannelNode(
                    default=config["email"]["default"],
                    configurable=config["email"]["configurable"],
                ),
                notification=ConfigurableEventChannelNode(
                    default=config["notification"]["default"],
                    configurable=config["notification"]["configurable"],
                ),
            ))

        return ConfigurableEventsNode(events=events)


@strawberry.type
@register_query()
class UserEventPreferenceQuery(Query):
    """GraphQL queries for user event preferences."""

    @lys_field(
        ensure_type=UserEventPreferencesNode,
        is_public=False,
        access_levels=[OWNER_ACCESS_LEVEL],
        is_licenced=False,
        description="Get all event preferences for the current user."
    )
    async def my_event_preferences(self, info: Info) -> UserEventPreferencesNode:
        """
        Get all event preferences for the authenticated user.

        Returns only preferences that the user has explicitly set.
        For events without preferences, the default values apply.
        """
        pref_service = info.context.app_manager.get_service("user_event_preference")
        user = info.context.connected_user
        session = info.context.session

        prefs = await pref_service.get_by_user(user["sub"], session)

        return UserEventPreferencesNode(
            preferences=[UserEventPreferenceNode.from_obj(p) for p in prefs]
        )


@strawberry.type
@register_mutation()
class UserEventPreferenceMutation(Mutation):
    """GraphQL mutations for user event preferences."""

    @lys_creation(
        ensure_type=UserEventPreferenceNode,
        is_public=False,
        access_levels=[CONNECTED_ACCESS_LEVEL],
        is_licenced=False,
        description="Create or update an event preference for the current user."
    )
    async def set_event_preference(
        self,
        inputs: SetEventPreferenceInput,
        info: Info
    ):
        """
        Set a user preference for an event channel.

        Creates a new preference or updates an existing one.
        Raises an error if the channel is blocked for this event.

        Args:
            inputs: Input containing:
                - event_type: The event type key (e.g., "FINANCIAL_IMPORT_COMPLETED")
                - channel: The channel type ("email" or "notification")
                - enabled: Whether to enable this channel
            info: GraphQL context

        Returns:
            UserEventPreference: The created or updated entity
        """
        # Convert Strawberry input to Pydantic model for validation
        input_data = inputs.to_pydantic()

        pref_service = info.context.app_manager.get_service("user_event_preference")
        user = info.context.connected_user
        session = info.context.session

        pref = await pref_service.create_or_update(
            user_id=user["sub"],
            event_type=input_data.event_type,
            channel=input_data.channel,
            enabled=input_data.enabled,
            session=session,
        )

        return pref
