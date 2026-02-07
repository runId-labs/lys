"""
Unit tests for licensing event type constants.
"""


class TestLicensingEventConstants:
    """Tests for licensing event type constants."""

    def test_license_granted_constant(self):
        from lys.apps.licensing.modules.event.consts import LICENSE_GRANTED
        assert LICENSE_GRANTED == "LICENSE_GRANTED"

    def test_license_revoked_constant(self):
        from lys.apps.licensing.modules.event.consts import LICENSE_REVOKED
        assert LICENSE_REVOKED == "LICENSE_REVOKED"

    def test_subscription_payment_success_constant(self):
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_PAYMENT_SUCCESS
        assert SUBSCRIPTION_PAYMENT_SUCCESS == "SUBSCRIPTION_PAYMENT_SUCCESS"

    def test_subscription_payment_failed_constant(self):
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_PAYMENT_FAILED
        assert SUBSCRIPTION_PAYMENT_FAILED == "SUBSCRIPTION_PAYMENT_FAILED"

    def test_subscription_canceled_constant(self):
        from lys.apps.licensing.modules.event.consts import SUBSCRIPTION_CANCELED
        assert SUBSCRIPTION_CANCELED == "SUBSCRIPTION_CANCELED"

    def test_all_constants_are_strings(self):
        from lys.apps.licensing.modules.event import consts
        for name in ["LICENSE_GRANTED", "LICENSE_REVOKED",
                     "SUBSCRIPTION_PAYMENT_SUCCESS", "SUBSCRIPTION_PAYMENT_FAILED",
                     "SUBSCRIPTION_CANCELED"]:
            assert isinstance(getattr(consts, name), str)

    def test_all_constants_unique(self):
        from lys.apps.licensing.modules.event import consts
        values = [
            consts.LICENSE_GRANTED,
            consts.LICENSE_REVOKED,
            consts.SUBSCRIPTION_PAYMENT_SUCCESS,
            consts.SUBSCRIPTION_PAYMENT_FAILED,
            consts.SUBSCRIPTION_CANCELED,
        ]
        assert len(values) == len(set(values))
