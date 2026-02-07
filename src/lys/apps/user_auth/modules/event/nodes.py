"""
GraphQL nodes for the event system.

Provides GraphQL types for:
- UserEventPreferenceNode: Individual user preference for an event channel
- ConfigurableEventNode: Event configuration for frontend display
- ConfigurableEventChannelNode: Channel configuration within an event
"""
from datetime import datetime
from typing import Optional, List

import strawberry
from strawberry import relay

from lys.apps.user_auth.modules.event.entities import UserEventPreference
from lys.apps.user_auth.modules.event.services import UserEventPreferenceService, EventService
from lys.core.graphql.nodes import EntityNode, ServiceNode
from lys.core.registries import register_node


@register_node()
class UserEventPreferenceNode(EntityNode[UserEventPreferenceService], relay.Node):
    """
    GraphQL node representing a user's preference for an event channel.

    Users can override default channel settings for specific events.
    """
    id: relay.NodeID[str]
    created_at: datetime
    updated_at: Optional[datetime]
    user_id: str
    event_type: str
    channel: str
    enabled: bool
    _entity: strawberry.Private[UserEventPreference]


@register_node()
class ConfigurableEventChannelNode(ServiceNode[EventService]):
    """
    Channel configuration within a configurable event.

    Indicates whether the channel is enabled by default and
    whether the user can modify it.
    """
    default: bool
    configurable: bool


@register_node()
class ConfigurableEventNode(ServiceNode[EventService]):
    """
    Event configuration for frontend display.

    Shows which channels are available and their configuration
    for a specific event type.
    """
    event_type: str
    email: ConfigurableEventChannelNode
    notification: ConfigurableEventChannelNode


@register_node()
class ConfigurableEventsNode(ServiceNode[EventService]):
    """
    Node containing all configurable events for the user preferences page.
    """
    events: List[ConfigurableEventNode]


@register_node()
class UserEventPreferencesNode(ServiceNode[EventService]):
    """
    Node containing all user event preferences.
    """
    preferences: List[UserEventPreferenceNode]