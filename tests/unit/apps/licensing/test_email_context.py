"""
Unit tests for email_context completeness in licensing trigger_event calls.

Verifies that each trigger_event call in the licensing app provides all
the context variables required by the corresponding email template.

Template variables are the source of truth. Each test checks that the
email_context dict keys cover all non-nullable variables used in the template.
"""
import ast
import os
import textwrap

import pytest
from jinja2 import Environment, FileSystemLoader


# =========================================================================
# Expected email_context keys per event type
# (derived from HTML templates — the source of truth)
# =========================================================================

# LICENSE_GRANTED: templates use {{ private_data.first_name }}, {{ client_name }},
# {{ license_name }}, {{ front_url }}
# private_data is injected by EmailingBatchService, front_url from fixture default.
# email_context provides: license_name, client_name
LICENSE_GRANTED_CONTEXT_KEYS = {"license_name", "client_name"}

# LICENSE_REVOKED: same as granted + optional {{ reason }}
LICENSE_REVOKED_CONTEXT_KEYS = {"license_name", "client_name"}

# SUBSCRIPTION_PAYMENT_SUCCESS: {{ client_name }}, {{ plan_name }}, {{ amount }},
# {{ currency }}, {{ billing_period }}, {{ next_billing_date }}, {{ front_url }}
SUBSCRIPTION_PAYMENT_SUCCESS_CONTEXT_KEYS = {
    "client_name", "plan_name", "amount", "currency",
    "billing_period", "next_billing_date", "front_url",
}

# SUBSCRIPTION_PAYMENT_FAILED: {{ client_name }}, {{ plan_name }}, {{ amount }},
# {{ currency }}, optional {{ error_reason }}, {{ front_url }}
SUBSCRIPTION_PAYMENT_FAILED_CONTEXT_KEYS = {
    "client_name", "plan_name", "amount", "currency",
    "error_reason", "front_url",
}

# SUBSCRIPTION_CANCELED: {{ client_name }}, {{ plan_name }},
# optional {{ effective_date }}, {{ front_url }}
SUBSCRIPTION_CANCELED_CONTEXT_KEYS = {
    "client_name", "plan_name", "effective_date", "front_url",
}


class TestLicenseGrantedEmailContext:
    """Verify LICENSE_GRANTED trigger_event provides required email_context."""

    def test_email_context_keys_in_user_service(self):
        """UserService.add_to_subscription email_context has required keys."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.user.services import UserService

        source = inspect.getsource(UserService.add_to_subscription)
        # Verify email_context dict contains expected keys
        for key in LICENSE_GRANTED_CONTEXT_KEYS:
            assert f'"{key}"' in source, (
                f"Missing '{key}' in LICENSE_GRANTED email_context"
            )

    def test_trigger_event_uses_license_granted_type(self):
        """Verify trigger_event is called with LICENSE_GRANTED event type."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.user.services import UserService

        source = inspect.getsource(UserService.add_to_subscription)
        assert "LICENSE_GRANTED" in source


class TestLicenseRevokedEmailContext:
    """Verify LICENSE_REVOKED trigger_event provides required email_context."""

    def test_email_context_keys_in_user_service(self):
        """UserService.remove_from_subscription email_context has required keys."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.user.services import UserService

        source = inspect.getsource(UserService.remove_from_subscription)
        for key in LICENSE_REVOKED_CONTEXT_KEYS:
            assert f'"{key}"' in source, (
                f"Missing '{key}' in LICENSE_REVOKED email_context"
            )

    def test_trigger_event_uses_license_revoked_type(self):
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.user.services import UserService

        source = inspect.getsource(UserService.remove_from_subscription)
        assert "LICENSE_REVOKED" in source


class TestSubscriptionPaymentSuccessEmailContext:
    """Verify SUBSCRIPTION_PAYMENT_SUCCESS trigger_event provides required email_context."""

    def test_email_context_keys_in_mollie_service(self):
        """MollieWebhookService._handle_payment_paid email_context has required keys."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService

        source = inspect.getsource(MollieWebhookService._handle_payment_paid)
        for key in SUBSCRIPTION_PAYMENT_SUCCESS_CONTEXT_KEYS:
            assert f'"{key}"' in source, (
                f"Missing '{key}' in SUBSCRIPTION_PAYMENT_SUCCESS email_context"
            )

    def test_trigger_event_uses_payment_success_type(self):
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService

        source = inspect.getsource(MollieWebhookService._handle_payment_paid)
        assert "SUBSCRIPTION_PAYMENT_SUCCESS" in source


class TestSubscriptionPaymentFailedEmailContext:
    """Verify SUBSCRIPTION_PAYMENT_FAILED trigger_event provides required email_context."""

    def test_email_context_keys_in_mollie_service(self):
        """MollieWebhookService._handle_payment_failed email_context has required keys."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService

        source = inspect.getsource(MollieWebhookService._handle_payment_failed)
        for key in SUBSCRIPTION_PAYMENT_FAILED_CONTEXT_KEYS:
            assert f'"{key}"' in source, (
                f"Missing '{key}' in SUBSCRIPTION_PAYMENT_FAILED email_context"
            )

    def test_trigger_event_uses_payment_failed_type(self):
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService

        source = inspect.getsource(MollieWebhookService._handle_payment_failed)
        assert "SUBSCRIPTION_PAYMENT_FAILED" in source


class TestSubscriptionCanceledEmailContext:
    """Verify SUBSCRIPTION_CANCELED trigger_event provides required email_context."""

    def test_email_context_keys_in_subscription_service(self):
        """SubscriptionService.cancel email_context has required keys."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        source = inspect.getsource(SubscriptionService.cancel)
        for key in SUBSCRIPTION_CANCELED_CONTEXT_KEYS:
            assert f'"{key}"' in source, (
                f"Missing '{key}' in SUBSCRIPTION_CANCELED email_context"
            )

    def test_trigger_event_uses_canceled_type(self):
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        source = inspect.getsource(SubscriptionService.cancel)
        assert "SUBSCRIPTION_CANCELED" in source


class TestEmailContextConsistencyAcrossEvents:
    """Cross-cutting tests to verify all events provide email_context."""

    def test_all_licensing_trigger_events_have_email_context(self):
        """All trigger_event calls in licensing include email_context parameter."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.user.services import UserService
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        methods = [
            UserService.add_to_subscription,
            UserService.remove_from_subscription,
            MollieWebhookService._handle_payment_paid,
            MollieWebhookService._handle_payment_failed,
            SubscriptionService.cancel,
        ]

        for method in methods:
            source = inspect.getsource(method)
            assert "email_context=" in source or "email_context =" in source, (
                f"{method.__qualname__} missing email_context in trigger_event call"
            )

    def test_all_licensing_trigger_events_have_notification_data(self):
        """All trigger_event calls in licensing include notification_data parameter."""
        import inspect
        pytest.importorskip("mollie", reason="mollie package not installed")
        from lys.apps.licensing.modules.user.services import UserService
        from lys.apps.licensing.modules.mollie.services import MollieWebhookService
        from lys.apps.licensing.modules.subscription.services import SubscriptionService

        methods = [
            UserService.add_to_subscription,
            UserService.remove_from_subscription,
            MollieWebhookService._handle_payment_paid,
            MollieWebhookService._handle_payment_failed,
            SubscriptionService.cancel,
        ]

        for method in methods:
            source = inspect.getsource(method)
            assert "notification_data=" in source or "notification_data =" in source, (
                f"{method.__qualname__} missing notification_data in trigger_event call"
            )
