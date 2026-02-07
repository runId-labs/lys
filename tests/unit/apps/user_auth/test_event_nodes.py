"""
Unit tests for user_auth event nodes.

Tests GraphQL node classes for the event system.
"""

from lys.apps.user_auth.modules.event.nodes import (
    UserEventPreferenceNode,
    ConfigurableEventChannelNode,
    ConfigurableEventNode,
    ConfigurableEventsNode,
    UserEventPreferencesNode,
)
from lys.core.graphql.nodes import EntityNode, ServiceNode


class TestUserEventPreferenceNode:
    """Tests for UserEventPreferenceNode class."""

    def test_class_exists(self):
        assert UserEventPreferenceNode is not None

    def test_inherits_from_entity_node(self):
        assert issubclass(UserEventPreferenceNode, EntityNode)

    def test_has_user_id_annotation(self):
        annotations = getattr(UserEventPreferenceNode, "__annotations__", {})
        assert "user_id" in annotations

    def test_has_event_type_annotation(self):
        annotations = getattr(UserEventPreferenceNode, "__annotations__", {})
        assert "event_type" in annotations

    def test_has_channel_annotation(self):
        annotations = getattr(UserEventPreferenceNode, "__annotations__", {})
        assert "channel" in annotations

    def test_has_enabled_annotation(self):
        annotations = getattr(UserEventPreferenceNode, "__annotations__", {})
        assert "enabled" in annotations

    def test_has_created_at_annotation(self):
        annotations = getattr(UserEventPreferenceNode, "__annotations__", {})
        assert "created_at" in annotations


class TestConfigurableEventChannelNode:
    """Tests for ConfigurableEventChannelNode class."""

    def test_class_exists(self):
        assert ConfigurableEventChannelNode is not None

    def test_inherits_from_service_node(self):
        assert issubclass(ConfigurableEventChannelNode, ServiceNode)

    def test_has_default_annotation(self):
        annotations = getattr(ConfigurableEventChannelNode, "__annotations__", {})
        assert "default" in annotations

    def test_has_configurable_annotation(self):
        annotations = getattr(ConfigurableEventChannelNode, "__annotations__", {})
        assert "configurable" in annotations


class TestConfigurableEventNode:
    """Tests for ConfigurableEventNode class."""

    def test_class_exists(self):
        assert ConfigurableEventNode is not None

    def test_inherits_from_service_node(self):
        assert issubclass(ConfigurableEventNode, ServiceNode)

    def test_has_event_type_annotation(self):
        annotations = getattr(ConfigurableEventNode, "__annotations__", {})
        assert "event_type" in annotations

    def test_has_email_annotation(self):
        annotations = getattr(ConfigurableEventNode, "__annotations__", {})
        assert "email" in annotations

    def test_has_notification_annotation(self):
        annotations = getattr(ConfigurableEventNode, "__annotations__", {})
        assert "notification" in annotations


class TestConfigurableEventsNode:
    """Tests for ConfigurableEventsNode class."""

    def test_class_exists(self):
        assert ConfigurableEventsNode is not None

    def test_inherits_from_service_node(self):
        assert issubclass(ConfigurableEventsNode, ServiceNode)

    def test_has_events_annotation(self):
        annotations = getattr(ConfigurableEventsNode, "__annotations__", {})
        assert "events" in annotations


class TestUserEventPreferencesNode:
    """Tests for UserEventPreferencesNode class."""

    def test_class_exists(self):
        assert UserEventPreferencesNode is not None

    def test_inherits_from_service_node(self):
        assert issubclass(UserEventPreferencesNode, ServiceNode)

    def test_has_preferences_annotation(self):
        annotations = getattr(UserEventPreferencesNode, "__annotations__", {})
        assert "preferences" in annotations
