"""Unit tests for discount arithmetic."""

import pytest

from lys.apps.licensing.consts import PERCENT_UNIT
from lys.apps.licensing.modules.discount.amounts import discounted_amount


class TestDiscountedAmount:
    """What a discount takes off an amount, in currency minor units."""

    def test_a_percentage_is_taken_off(self):
        assert discounted_amount(790000, 30, PERCENT_UNIT) == 553000

    def test_the_reduction_is_floored(self):
        # 30% of 9.99 EUR is 2.997: 2.99 is taken off, not 3.00
        assert discounted_amount(999, 30, PERCENT_UNIT) == 700

    def test_a_full_discount_owes_nothing(self):
        assert discounted_amount(50000, 100, PERCENT_UNIT) == 0

    def test_a_value_above_the_maximum_never_owes_the_client(self):
        assert discounted_amount(50000, 150, PERCENT_UNIT) == 0

    def test_no_discount_leaves_the_amount_untouched(self):
        assert discounted_amount(50000, 0, PERCENT_UNIT) == 50000

    def test_an_unknown_unit_is_refused(self):
        """A unit added to the reference data without being handled here would
        otherwise silently charge the full price."""
        with pytest.raises(ValueError, match="Unsupported discount unit"):
            discounted_amount(50000, 30, "AMOUNT")


class _Currency:
    minor_unit = 2

    @staticmethod
    def to_major_unit(amount):
        return amount / 100


class _Commitment:
    duration_months = 12


class _PlanVersion:
    id = "version-1"
    plan_id = "PRO"
    version = 1


class _Price:
    id = "price-1"
    amount = 30000
    currency_id = "EUR"
    period_id = "YEARLY"
    commitment_id = "ONE_YEAR"
    plan_version_id = "version-1"
    plan_version = _PlanVersion()
    commitment = _Commitment()
    currency = _Currency()


class _Granted:
    discount_id = "FC_DISCOUNT"
    value = 30
    unit_id = PERCENT_UNIT


class TestSettleTerms:
    """What is owed, and the receipt that justifies it."""

    def test_settling_without_a_discount_owes_the_catalogue_price(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        amount_due, receipt = SubscriptionService.settle(_Price(), None, None)

        assert amount_due == 30000
        assert receipt["discount"] is None
        assert receipt["price"]["currency"] == "EUR"

    def test_settling_with_a_discount_applies_it(self):
        """What the renewal relies on: a discount that was not removed must not
        vanish from the amount owed."""
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        amount_due, receipt = SubscriptionService.settle(_Price(), _Granted(), None)

        assert amount_due == 21000
        assert receipt["discount"]["id"] == "FC_DISCOUNT"

    def test_a_free_subscription_owes_nothing(self):
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        assert SubscriptionService.settle(None, None, None) == (None, None)
