"""
Unit tests for Mollie Strawberry input types.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestSubscribeToPlanInput:
    """Tests for SubscribeToPlanInput Strawberry input."""

    def test_input_exists(self):
        from lys.apps.licensing.modules.mollie.inputs import SubscribeToPlanInput
        assert SubscribeToPlanInput is not None

    def test_is_strawberry_input(self):
        from lys.apps.licensing.modules.mollie.inputs import SubscribeToPlanInput
        assert hasattr(SubscribeToPlanInput, "__strawberry_definition__") or hasattr(SubscribeToPlanInput, "_pydantic_type")


class TestBillingPeriodGQL:
    """Tests for BillingPeriodGQL Strawberry enum."""

    def test_enum_exists(self):
        from lys.apps.licensing.modules.mollie.inputs import BillingPeriodGQL
        assert BillingPeriodGQL is not None
