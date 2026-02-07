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
    """Tests for EventService.should_send() method signature."""

    def test_should_send_signature(self):
        import inspect
        from lys.apps.user_auth.modules.event.services import EventService
        sig = inspect.signature(EventService.should_send)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "event_type" in params
        assert "channel" in params
        assert "session" in params
