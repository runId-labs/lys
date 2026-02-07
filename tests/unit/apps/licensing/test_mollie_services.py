"""
Unit tests for Mollie service structure and utility functions.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestMollieWebhookServiceStructure:
    """Tests for MollieWebhookService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        assert MollieWebhookService is not None

    def test_inherits_from_service(self):
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        from lys.core.services import Service
        assert issubclass(MollieWebhookService, Service)

    def test_service_name(self):
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        assert MollieWebhookService.service_name == "mollie_webhook"

    def test_has_handle_webhook_method(self):
        import inspect
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        assert hasattr(MollieWebhookService, "handle_webhook")
        assert inspect.iscoroutinefunction(MollieWebhookService.handle_webhook)

    def test_payment_handlers_dict(self):
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        assert "paid" in MollieWebhookService.PAYMENT_HANDLERS
        assert "failed" in MollieWebhookService.PAYMENT_HANDLERS
        assert "expired" in MollieWebhookService.PAYMENT_HANDLERS
        assert "canceled" in MollieWebhookService.PAYMENT_HANDLERS

    def test_subscription_handlers_dict(self):
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        assert "active" in MollieWebhookService.SUBSCRIPTION_HANDLERS
        assert "pending" in MollieWebhookService.SUBSCRIPTION_HANDLERS
        assert "canceled" in MollieWebhookService.SUBSCRIPTION_HANDLERS
        assert "suspended" in MollieWebhookService.SUBSCRIPTION_HANDLERS
        assert "completed" in MollieWebhookService.SUBSCRIPTION_HANDLERS


class TestMollieCheckoutServiceStructure:
    """Tests for MollieCheckoutService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.mollie.services import MollieCheckoutService
        assert MollieCheckoutService is not None

    def test_inherits_from_service(self):
        from lys.apps.licensing.modules.mollie.services import MollieCheckoutService
        from lys.core.services import Service
        assert issubclass(MollieCheckoutService, Service)

    def test_service_name(self):
        from lys.apps.licensing.modules.mollie.services import MollieCheckoutService
        assert MollieCheckoutService.service_name == "mollie_checkout"

    def test_has_create_payment_method(self):
        import inspect
        from lys.apps.licensing.modules.mollie.services import MollieCheckoutService
        assert hasattr(MollieCheckoutService, "create_payment")
        assert inspect.iscoroutinefunction(MollieCheckoutService.create_payment)

    def test_has_create_subscription_method(self):
        import inspect
        from lys.apps.licensing.modules.mollie.services import MollieCheckoutService
        assert hasattr(MollieCheckoutService, "create_subscription")
        assert inspect.iscoroutinefunction(MollieCheckoutService.create_subscription)


class TestMollieUtilityFunctions:
    """Tests for Mollie utility functions."""

    def test_get_payment_config_returns_dict(self):
        from lys.apps.licensing.modules.mollie.services import get_payment_config
        config = get_payment_config()
        assert isinstance(config, dict)

    def test_is_payment_configured_returns_bool(self):
        from lys.apps.licensing.modules.mollie.services import is_payment_configured
        result = is_payment_configured()
        assert isinstance(result, bool)

    def test_get_payment_provider_returns_string_or_none(self):
        from lys.apps.licensing.modules.mollie.services import get_payment_provider
        result = get_payment_provider()
        assert result is None or isinstance(result, str)

    def test_get_webhook_base_url_returns_string_or_none(self):
        from lys.apps.licensing.modules.mollie.services import get_webhook_base_url
        result = get_webhook_base_url()
        assert result is None or isinstance(result, str)

    def test_get_mollie_client_without_config_returns_none(self):
        from lys.apps.licensing.modules.mollie.services import get_mollie_client
        result = get_mollie_client()
        assert result is None
