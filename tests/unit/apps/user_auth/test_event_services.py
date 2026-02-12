"""
Unit tests for user_auth event services.
"""
import inspect


class TestUserEventPreferenceServiceStructure:
    """Tests for UserEventPreferenceService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.event.services import UserEventPreferenceService
        assert UserEventPreferenceService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.user_auth.modules.event.services import UserEventPreferenceService
        from lys.core.services import EntityService
        assert issubclass(UserEventPreferenceService, EntityService)

    def test_has_create_or_update_method(self):
        from lys.apps.user_auth.modules.event.services import UserEventPreferenceService
        assert hasattr(UserEventPreferenceService, "create_or_update")
        assert inspect.iscoroutinefunction(UserEventPreferenceService.create_or_update)

    def test_has_get_by_user_method(self):
        from lys.apps.user_auth.modules.event.services import UserEventPreferenceService
        assert hasattr(UserEventPreferenceService, "get_by_user")
        assert inspect.iscoroutinefunction(UserEventPreferenceService.get_by_user)


class TestEventServiceStructure:
    """Tests for base EventService class structure."""

    def test_service_exists(self):
        from lys.apps.user_auth.modules.event.services import EventService
        assert EventService is not None

    def test_has_get_channels_method(self):
        from lys.apps.user_auth.modules.event.services import EventService
        assert hasattr(EventService, "get_channels")
        assert callable(EventService.get_channels)

    def test_has_should_send_method(self):
        from lys.apps.user_auth.modules.event.services import EventService
        assert hasattr(EventService, "should_send")

    def test_has_get_user_configurable_events_method(self):
        from lys.apps.user_auth.modules.event.services import EventService
        assert hasattr(EventService, "get_user_configurable_events")


class TestEventServiceChannels:
    """Tests for EventService.get_channels() content."""

    def test_get_channels_returns_dict(self):
        from lys.apps.user_auth.modules.event.services import EventService
        channels = EventService.get_channels()
        assert isinstance(channels, dict)

    def test_channels_contain_user_invited(self):
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import USER_INVITED
        channels = EventService.get_channels()
        assert USER_INVITED in channels

    def test_channels_contain_email_verification(self):
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import USER_EMAIL_VERIFICATION_REQUESTED
        channels = EventService.get_channels()
        assert USER_EMAIL_VERIFICATION_REQUESTED in channels

    def test_channels_contain_password_reset(self):
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import USER_PASSWORD_RESET_REQUESTED
        channels = EventService.get_channels()
        assert USER_PASSWORD_RESET_REQUESTED in channels

    def test_channel_entries_have_required_keys(self):
        from lys.apps.user_auth.modules.event.services import EventService
        channels = EventService.get_channels()
        for event_type, config in channels.items():
            assert "email" in config, f"{event_type} missing 'email' key"
            assert "notification" in config, f"{event_type} missing 'notification' key"
            assert "blocked" in config, f"{event_type} missing 'blocked' key"

    def test_blocked_is_list(self):
        from lys.apps.user_auth.modules.event.services import EventService
        channels = EventService.get_channels()
        for event_type, config in channels.items():
            assert isinstance(config["blocked"], list), f"{event_type} blocked is not a list"


class TestEventServiceShouldSend:
    """Tests for EventService.should_send() method signature and logic."""

    def test_should_send_signature(self):
        import inspect
        from lys.apps.user_auth.modules.event.services import EventService
        sig = inspect.signature(EventService.should_send)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "event_type" in params
        assert "channel" in params
        assert "session" in params

    def test_should_send_returns_false_for_unknown_event(self):
        """Test should_send returns False for unknown event type."""
        from lys.apps.user_auth.modules.event.services import EventService
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_app_manager = MagicMock()
        mock_app_manager.get_entity.return_value = MagicMock()

        with patch.object(EventService, "app_manager", mock_app_manager):
            result = EventService.should_send(
                user_id="user-123",
                event_type="NONEXISTENT_EVENT",
                channel="email",
                session=mock_session
            )
        assert result is False

    def test_should_send_returns_default_when_no_preference(self):
        """Test should_send returns default value when no user preference exists."""
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import USER_INVITED
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_pref_entity = MagicMock()
        # No preference found
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        mock_app_manager = MagicMock()
        mock_app_manager.get_entity.return_value = mock_pref_entity

        with patch.object(EventService, "app_manager", mock_app_manager):
            result = EventService.should_send(
                user_id="user-123",
                event_type=USER_INVITED,
                channel="email",
                session=mock_session
            )
        # USER_INVITED has email=True as default
        assert result is True

    def test_should_send_returns_preference_when_exists(self):
        """Test should_send returns user preference when it exists."""
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import USER_INVITED
        from unittest.mock import MagicMock, patch

        mock_pref = MagicMock()
        mock_pref.enabled = False

        mock_session = MagicMock()
        mock_pref_entity = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_pref

        mock_app_manager = MagicMock()
        mock_app_manager.get_entity.return_value = mock_pref_entity

        with patch.object(EventService, "app_manager", mock_app_manager):
            result = EventService.should_send(
                user_id="user-123",
                event_type=USER_INVITED,
                channel="email",
                session=mock_session
            )
        # User preference overrides default
        assert result is False


class TestEventServiceGetUserConfigurableEvents:
    """Tests for EventService.get_user_configurable_events() logic."""

    def test_returns_configurable_events(self):
        """Test that get_user_configurable_events returns events with at least one non-blocked channel."""
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import (
            USER_INVITED,
            USER_EMAIL_VERIFICATION_REQUESTED,
            USER_PASSWORD_RESET_REQUESTED,
        )
        configurable = EventService.get_user_configurable_events()

        # USER_INVITED has email blocked, but notification is not blocked → configurable
        assert USER_INVITED in configurable
        # USER_EMAIL_VERIFICATION_REQUESTED has email blocked, notification not blocked → configurable
        assert USER_EMAIL_VERIFICATION_REQUESTED in configurable
        # USER_PASSWORD_RESET_REQUESTED has both email and notification blocked → NOT configurable
        assert USER_PASSWORD_RESET_REQUESTED not in configurable

    def test_configurable_events_have_channel_info(self):
        """Test that configurable events have email and notification info."""
        from lys.apps.user_auth.modules.event.services import EventService
        configurable = EventService.get_user_configurable_events()

        for event_type, config in configurable.items():
            assert "email" in config
            assert "notification" in config
            assert "default" in config["email"]
            assert "configurable" in config["email"]
            assert "default" in config["notification"]
            assert "configurable" in config["notification"]

    def test_blocked_channels_are_not_configurable(self):
        """Test that blocked channels are marked as not configurable."""
        from lys.apps.user_auth.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.consts import USER_INVITED
        configurable = EventService.get_user_configurable_events()

        # USER_INVITED has email blocked
        assert configurable[USER_INVITED]["email"]["configurable"] is False
        # USER_INVITED notification is not blocked
        assert configurable[USER_INVITED]["notification"]["configurable"] is True
