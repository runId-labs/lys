"""
Unit tests for licensing event service.
"""


class TestLicensingEventServiceStructure:
    """Tests for licensing EventService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.event.services import EventService
        assert EventService is not None

    def test_inherits_from_base_event_service(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.services import EventService as BaseEventService
        assert issubclass(EventService, BaseEventService)

    def test_has_get_channels_method(self):
        from lys.apps.licensing.modules.event.services import EventService
        assert hasattr(EventService, "get_channels")
        assert callable(EventService.get_channels)


class TestLicensingEventServiceChannels:
    """Tests for licensing EventService.get_channels()."""

    def test_get_channels_returns_dict(self):
        from lys.apps.licensing.modules.event.services import EventService
        channels = EventService.get_channels()
        assert isinstance(channels, dict)

    def test_channels_contain_license_granted(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED
        channels = EventService.get_channels()
        assert LICENSE_GRANTED in channels

    def test_channels_contain_license_revoked(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import LICENSE_REVOKED
        channels = EventService.get_channels()
        assert LICENSE_REVOKED in channels

    def test_channels_contain_subscription_payment_success(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_PAYMENT_SUCCESS
        channels = EventService.get_channels()
        assert SUBSCRIPTION_PAYMENT_SUCCESS in channels

    def test_channels_contain_subscription_payment_failed(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_PAYMENT_FAILED
        channels = EventService.get_channels()
        assert SUBSCRIPTION_PAYMENT_FAILED in channels

    def test_channels_contain_subscription_canceled(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_CANCELED
        channels = EventService.get_channels()
        assert SUBSCRIPTION_CANCELED in channels

    def test_license_granted_has_email_enabled(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED
        channels = EventService.get_channels()
        assert channels[LICENSE_GRANTED]["email"] is True

    def test_license_granted_has_notification_enabled(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED
        channels = EventService.get_channels()
        assert channels[LICENSE_GRANTED]["notification"] is True

    def test_license_granted_is_configurable(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED
        channels = EventService.get_channels()
        assert channels[LICENSE_GRANTED]["blocked"] == []

    def test_license_revoked_is_mandatory(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import LICENSE_REVOKED
        channels = EventService.get_channels()
        assert "email" in channels[LICENSE_REVOKED]["blocked"]
        assert "notification" in channels[LICENSE_REVOKED]["blocked"]

    def test_subscription_payment_failed_is_mandatory(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_PAYMENT_FAILED
        channels = EventService.get_channels()
        assert "email" in channels[SUBSCRIPTION_PAYMENT_FAILED]["blocked"]
        assert "notification" in channels[SUBSCRIPTION_PAYMENT_FAILED]["blocked"]

    def test_subscription_canceled_is_configurable(self):
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_CANCELED
        channels = EventService.get_channels()
        assert channels[SUBSCRIPTION_CANCELED]["blocked"] == []

    def test_inherits_base_event_channels(self):
        """Licensing EventService should include base user_auth event channels."""
        from lys.apps.licensing.modules.event.services import EventService
        from lys.apps.user_auth.modules.event.services import EventService as BaseEventService
        base_channels = BaseEventService.get_channels()
        licensing_channels = EventService.get_channels()
        for key in base_channels:
            assert key in licensing_channels
