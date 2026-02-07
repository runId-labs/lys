"""
Unit tests for licensing emailing type constants.
"""


class TestLicensingEmailingConstants:
    """Tests for licensing emailing type constants."""

    def test_license_granted_emailing_type(self):
        from lys.apps.licensing.modules.emailing.consts import LICENSE_GRANTED_EMAILING_TYPE
        assert LICENSE_GRANTED_EMAILING_TYPE == "LICENSE_GRANTED"

    def test_license_revoked_emailing_type(self):
        from lys.apps.licensing.modules.emailing.consts import LICENSE_REVOKED_EMAILING_TYPE
        assert LICENSE_REVOKED_EMAILING_TYPE == "LICENSE_REVOKED"

    def test_subscription_payment_success_emailing_type(self):
        from lys.apps.licensing.modules.emailing.consts import SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE
        assert SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE == "SUBSCRIPTION_PAYMENT_SUCCESS"

    def test_subscription_payment_failed_emailing_type(self):
        from lys.apps.licensing.modules.emailing.consts import SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE
        assert SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE == "SUBSCRIPTION_PAYMENT_FAILED"

    def test_subscription_canceled_emailing_type(self):
        from lys.apps.licensing.modules.emailing.consts import SUBSCRIPTION_CANCELED_EMAILING_TYPE
        assert SUBSCRIPTION_CANCELED_EMAILING_TYPE == "SUBSCRIPTION_CANCELED"

    def test_emailing_types_match_event_consts(self):
        """Emailing types must match event constants for unified event system."""
        from lys.apps.licensing.modules.emailing import consts as emailing_consts
        from lys.apps.licensing.modules.event import consts as event_consts

        assert emailing_consts.LICENSE_GRANTED_EMAILING_TYPE == event_consts.LICENSE_GRANTED
        assert emailing_consts.LICENSE_REVOKED_EMAILING_TYPE == event_consts.LICENSE_REVOKED
        assert emailing_consts.SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE == event_consts.SUBSCRIPTION_PAYMENT_SUCCESS
        assert emailing_consts.SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE == event_consts.SUBSCRIPTION_PAYMENT_FAILED
        assert emailing_consts.SUBSCRIPTION_CANCELED_EMAILING_TYPE == event_consts.SUBSCRIPTION_CANCELED
