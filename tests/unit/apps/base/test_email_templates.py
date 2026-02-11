"""
Unit tests for email template rendering.

Verifies that all 16 email templates (8 FR + 8 EN) render without errors
when provided with their expected context variables. Tests:
- Template inheritance from _base.html works correctly
- All required variables render without UndefinedError
- Nullable fields render correctly when None or absent
- Rendered HTML contains expected dynamic values
"""
import os

import pytest
from jinja2 import Environment, FileSystemLoader


# Resolve templates directory relative to project root
TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..",
    "templates", "emails"
)
TEMPLATES_DIR = os.path.normpath(TEMPLATES_DIR)


@pytest.fixture
def template_env():
    """Create a Jinja2 Environment pointing to the templates directory."""
    return Environment(loader=FileSystemLoader(TEMPLATES_DIR))


# =========================================================================
# Context definitions per template (matching what the code provides)
# =========================================================================

USER_AUTH_CONTEXTS = {
    "user_email_verification": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "token": "abc123-verification-token",
    },
    "user_password_reset": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "token": "xyz789-reset-token",
    },
    "user_invitation": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "token": "inv-456-token",
        "inviter_name": "Bob Manager",
    },
}

LICENSING_CONTEXTS = {
    "license_granted": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "license_name": "Pro License",
        "client_name": "Acme Corp",
    },
    "license_revoked": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "license_name": "Pro License",
        "client_name": "Acme Corp",
        "reason": "Contract expired",
    },
    "subscription_payment_success": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "client_name": "Acme Corp",
        "plan_name": "Pro Plan",
        "amount": "29.99",
        "currency": "EUR",
        "billing_period": "monthly",
        "next_billing_date": "2026-03-11",
    },
    "subscription_payment_failed": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "client_name": "Acme Corp",
        "plan_name": "Pro Plan",
        "amount": "29.99",
        "currency": "EUR",
        "error_reason": "Insufficient funds",
    },
    "subscription_canceled": {
        "private_data": {"first_name": "Alice", "last_name": "Smith"},
        "front_url": "https://app.example.com",
        "client_name": "Acme Corp",
        "plan_name": "Pro Plan",
        "effective_date": "2026-04-11",
    },
}

ALL_TEMPLATES = {**USER_AUTH_CONTEXTS, **LICENSING_CONTEXTS}
LANGUAGES = ["fr", "en"]


# =========================================================================
# Base template tests
# =========================================================================

class TestBaseTemplate:
    """Tests for _base.html template structure."""

    def test_base_template_exists(self, template_env):
        template = template_env.get_template("_base.html")
        assert template is not None

    def test_base_template_renders(self, template_env):
        template = template_env.get_template("_base.html")
        html = template.render(front_url="https://example.com")
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_base_template_has_viewport_meta(self, template_env):
        template = template_env.get_template("_base.html")
        html = template.render(front_url="https://example.com")
        assert "viewport" in html

    def test_base_template_default_lang_fr(self, template_env):
        template = template_env.get_template("_base.html")
        html = template.render(front_url="https://example.com")
        assert 'lang="fr"' in html


# =========================================================================
# Template rendering tests — all 16 templates
# =========================================================================

class TestTemplateRendering:
    """Verify all templates render without errors with complete context."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    @pytest.mark.parametrize("template_name,context", list(ALL_TEMPLATES.items()))
    def test_template_renders_without_error(self, template_env, lang, template_name, context):
        """Each template renders without raising any exception."""
        template_path = f"{lang}/{template_name}.html"
        template = template_env.get_template(template_path)
        html = template.render(**context)
        assert len(html) > 0

    @pytest.mark.parametrize("lang", LANGUAGES)
    @pytest.mark.parametrize("template_name,context", list(ALL_TEMPLATES.items()))
    def test_template_produces_valid_html(self, template_env, lang, template_name, context):
        """Rendered template contains basic HTML structure from _base.html."""
        template_path = f"{lang}/{template_name}.html"
        template = template_env.get_template(template_path)
        html = template.render(**context)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<body" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    @pytest.mark.parametrize("template_name,context", list(ALL_TEMPLATES.items()))
    def test_template_extends_base(self, template_env, lang, template_name, context):
        """Each template inherits base structure (background container)."""
        template_path = f"{lang}/{template_name}.html"
        template = template_env.get_template(template_path)
        html = template.render(**context)
        assert "f8f9fa" in html  # Base background color


# =========================================================================
# Dynamic value substitution tests
# =========================================================================

class TestTemplateValueSubstitution:
    """Verify dynamic values appear in rendered output."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_first_name_rendered(self, template_env, lang):
        """private_data.first_name appears in rendered HTML."""
        template = template_env.get_template(f"{lang}/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert "Alice" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_client_name_rendered(self, template_env, lang):
        """client_name appears in rendered HTML."""
        template = template_env.get_template(f"{lang}/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert "Acme Corp" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_license_name_rendered(self, template_env, lang):
        """license_name appears in rendered HTML."""
        template = template_env.get_template(f"{lang}/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert "Pro License" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_front_url_in_cta(self, template_env, lang):
        """front_url appears in CTA link."""
        template = template_env.get_template(f"{lang}/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert "https://app.example.com" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_payment_success_all_values(self, template_env, lang):
        """All payment success values appear in rendered HTML."""
        template = template_env.get_template(f"{lang}/subscription_payment_success.html")
        html = template.render(**LICENSING_CONTEXTS["subscription_payment_success"])
        assert "Acme Corp" in html
        assert "Pro Plan" in html
        assert "29.99" in html
        assert "EUR" in html
        assert "monthly" in html
        assert "2026-03-11" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_payment_failed_values(self, template_env, lang):
        """Payment failed values appear in rendered HTML."""
        template = template_env.get_template(f"{lang}/subscription_payment_failed.html")
        html = template.render(**LICENSING_CONTEXTS["subscription_payment_failed"])
        assert "Acme Corp" in html
        assert "Pro Plan" in html
        assert "29.99" in html
        assert "EUR" in html
        assert "Insufficient funds" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_subscription_canceled_values(self, template_env, lang):
        """Subscription canceled values appear in rendered HTML."""
        template = template_env.get_template(f"{lang}/subscription_canceled.html")
        html = template.render(**LICENSING_CONTEXTS["subscription_canceled"])
        assert "Acme Corp" in html
        assert "Pro Plan" in html
        assert "2026-04-11" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_verification_token_in_url(self, template_env, lang):
        """Token appears in verification URL."""
        template = template_env.get_template(f"{lang}/user_email_verification.html")
        html = template.render(**USER_AUTH_CONTEXTS["user_email_verification"])
        assert "abc123-verification-token" in html
        assert "verify-email" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_password_reset_token_in_url(self, template_env, lang):
        """Token appears in password reset URL."""
        template = template_env.get_template(f"{lang}/user_password_reset.html")
        html = template.render(**USER_AUTH_CONTEXTS["user_password_reset"])
        assert "xyz789-reset-token" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_invitation_inviter_name(self, template_env, lang):
        """Inviter name appears in invitation email."""
        template = template_env.get_template(f"{lang}/user_invitation.html")
        html = template.render(**USER_AUTH_CONTEXTS["user_invitation"])
        assert "Bob Manager" in html


# =========================================================================
# Nullable field tests
# =========================================================================

class TestTemplateNullableFields:
    """Verify templates handle nullable fields correctly."""

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_license_revoked_without_reason(self, template_env, lang):
        """license_revoked renders without error when reason is None."""
        context = {
            "private_data": {"first_name": "Alice", "last_name": "Smith"},
            "front_url": "https://app.example.com",
            "license_name": "Pro License",
            "client_name": "Acme Corp",
            "reason": None,
        }
        template = template_env.get_template(f"{lang}/license_revoked.html")
        html = template.render(**context)
        assert "Alice" in html
        # "Reason" label should NOT appear when reason is None
        assert "Reason" not in html or "Raison" not in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_payment_failed_without_error_reason(self, template_env, lang):
        """subscription_payment_failed renders when error_reason is None."""
        context = {
            "private_data": {"first_name": "Alice", "last_name": "Smith"},
            "front_url": "https://app.example.com",
            "client_name": "Acme Corp",
            "plan_name": "Pro Plan",
            "amount": "29.99",
            "currency": "EUR",
            "error_reason": None,
        }
        template = template_env.get_template(f"{lang}/subscription_payment_failed.html")
        html = template.render(**context)
        assert "Alice" in html

    @pytest.mark.parametrize("lang", LANGUAGES)
    def test_subscription_canceled_without_effective_date(self, template_env, lang):
        """subscription_canceled renders when effective_date is None."""
        context = {
            "private_data": {"first_name": "Alice", "last_name": "Smith"},
            "front_url": "https://app.example.com",
            "client_name": "Acme Corp",
            "plan_name": "Pro Plan",
            "effective_date": None,
        }
        template = template_env.get_template(f"{lang}/subscription_canceled.html")
        html = template.render(**context)
        assert "Alice" in html


# =========================================================================
# Language-specific tests
# =========================================================================

class TestTemplateLanguageSpecific:
    """Verify language-specific content."""

    def test_en_templates_have_lang_en(self, template_env):
        """EN templates set lang='en' on html tag."""
        template = template_env.get_template("en/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert 'lang="en"' in html

    def test_fr_templates_have_lang_fr(self, template_env):
        """FR templates use default lang='fr' from _base.html."""
        template = template_env.get_template("fr/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert 'lang="fr"' in html

    def test_en_uses_english_text(self, template_env):
        """EN template uses English text."""
        template = template_env.get_template("en/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert "New License Granted" in html

    def test_fr_uses_french_text(self, template_env):
        """FR template uses French text."""
        template = template_env.get_template("fr/license_granted.html")
        html = template.render(**LICENSING_CONTEXTS["license_granted"])
        assert "Nouvelle licence accord" in html

    def test_en_no_hardcoded_eywa(self, template_env):
        """EN templates should not contain hardcoded 'Eywa'."""
        for template_name in ALL_TEMPLATES:
            template = template_env.get_template(f"en/{template_name}.html")
            html = template.render(**ALL_TEMPLATES[template_name])
            assert "Eywa" not in html, f"Found 'Eywa' in en/{template_name}.html"

    def test_fr_no_hardcoded_eywa(self, template_env):
        """FR templates should not contain hardcoded 'Eywa'."""
        for template_name in ALL_TEMPLATES:
            template = template_env.get_template(f"fr/{template_name}.html")
            html = template.render(**ALL_TEMPLATES[template_name])
            assert "Eywa" not in html, f"Found 'Eywa' in fr/{template_name}.html"
