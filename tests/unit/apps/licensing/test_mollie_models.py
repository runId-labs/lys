"""
Unit tests for Mollie Pydantic models.
"""
from dataclasses import fields as dc_fields

import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestSubscribeToPlanResult:
    """Tests for SubscribeToPlanResult dataclass."""

    def test_class_exists(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        assert SubscribeToPlanResult is not None

    def test_has_success_field(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        field_names = [f.name for f in dc_fields(SubscribeToPlanResult)]
        assert "success" in field_names

    def test_has_checkout_url_field(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        field_names = [f.name for f in dc_fields(SubscribeToPlanResult)]
        assert "checkout_url" in field_names

    def test_has_effective_date_field(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        field_names = [f.name for f in dc_fields(SubscribeToPlanResult)]
        assert "effective_date" in field_names

    def test_has_prorata_amount_field(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        field_names = [f.name for f in dc_fields(SubscribeToPlanResult)]
        assert "prorata_amount" in field_names

    def test_has_error_field(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        field_names = [f.name for f in dc_fields(SubscribeToPlanResult)]
        assert "error" in field_names

    def test_defaults_optional_fields_to_none(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        result = SubscribeToPlanResult(success=True)
        assert result.checkout_url is None
        assert result.effective_date is None
        assert result.prorata_amount is None
        assert result.error is None

    def test_success_field_required(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanResult
        with pytest.raises(TypeError):
            SubscribeToPlanResult()


class TestCancelSubscriptionResult:
    """Tests for CancelSubscriptionResult dataclass."""

    def test_class_exists(self):
        from lys.apps.licensing.modules.mollie.models import CancelSubscriptionResult
        assert CancelSubscriptionResult is not None

    def test_has_success_field(self):
        from lys.apps.licensing.modules.mollie.models import CancelSubscriptionResult
        field_names = [f.name for f in dc_fields(CancelSubscriptionResult)]
        assert "success" in field_names

    def test_has_effective_date_field(self):
        from lys.apps.licensing.modules.mollie.models import CancelSubscriptionResult
        field_names = [f.name for f in dc_fields(CancelSubscriptionResult)]
        assert "effective_date" in field_names

    def test_has_error_field(self):
        from lys.apps.licensing.modules.mollie.models import CancelSubscriptionResult
        field_names = [f.name for f in dc_fields(CancelSubscriptionResult)]
        assert "error" in field_names

    def test_defaults_to_none(self):
        from lys.apps.licensing.modules.mollie.models import CancelSubscriptionResult
        result = CancelSubscriptionResult(success=False)
        assert result.effective_date is None
        assert result.error is None


class TestSubscribeToPlanInputModel:
    """Tests for SubscribeToPlanInputModel Pydantic model."""

    def test_model_exists(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel
        assert SubscribeToPlanInputModel is not None

    def test_valid_input(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel
        model = SubscribeToPlanInputModel(
            plan_version_id="some-uuid",
            billing_period="monthly",
            success_url="https://example.com/success"
        )
        assert model.plan_version_id == "some-uuid"
        assert model.success_url == "https://example.com/success"

    def test_plan_version_id_from_string(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel
        model = SubscribeToPlanInputModel(
            plan_version_id="test-id",
            billing_period="monthly",
            success_url="https://example.com"
        )
        assert model.plan_version_id == "test-id"

    def test_plan_version_id_from_dict(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel
        model = SubscribeToPlanInputModel(
            plan_version_id={"node_id": "extracted-id"},
            billing_period="monthly",
            success_url="https://example.com"
        )
        assert model.plan_version_id == "extracted-id"

    def test_billing_period_monthly(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel
        from lys.apps.licensing.consts import BillingPeriod
        model = SubscribeToPlanInputModel(
            plan_version_id="id",
            billing_period="monthly",
            success_url="https://example.com"
        )
        assert model.billing_period == BillingPeriod.MONTHLY

    def test_billing_period_yearly(self):
        from lys.apps.licensing.modules.mollie.models import SubscribeToPlanInputModel
        from lys.apps.licensing.consts import BillingPeriod
        model = SubscribeToPlanInputModel(
            plan_version_id="id",
            billing_period="yearly",
            success_url="https://example.com"
        )
        assert model.billing_period == BillingPeriod.YEARLY
