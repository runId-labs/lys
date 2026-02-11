"""
Unit tests for licensing emailing fixtures context_description alignment.

Verifies that:
- Each fixture's context_description keys match template variables
- Subscription types have roles: [LICENSE_ADMIN_ROLE]
- License types have appropriate context_description
"""
import os

import pytest
from jinja2 import Environment, FileSystemLoader

from lys.apps.licensing.modules.emailing.consts import (
    LICENSE_GRANTED_EMAILING_TYPE,
    LICENSE_REVOKED_EMAILING_TYPE,
    SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE,
    SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE,
    SUBSCRIPTION_CANCELED_EMAILING_TYPE,
)
from lys.apps.licensing.modules.emailing.fixtures import EmailingTypeFixtures


def _get_fixture_by_id(type_id):
    """Find a fixture entry by its ID."""
    for entry in EmailingTypeFixtures.data_list:
        if entry["id"] == type_id:
            return entry
    return None


# =========================================================================
# Context description keys per type
# =========================================================================

# Expected keys in context_description (non-user keys that appear in templates)
# Note: "user" key describes private_data extraction for compute_context path
EXPECTED_CONTEXT_KEYS = {
    LICENSE_GRANTED_EMAILING_TYPE: {
        "front_url", "license_name", "client_name",
    },
    LICENSE_REVOKED_EMAILING_TYPE: {
        "front_url", "license_name", "client_name", "reason",
    },
    SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE: {
        "front_url", "client_name", "plan_name", "amount", "currency",
        "billing_period", "next_billing_date",
    },
    SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE: {
        "front_url", "client_name", "plan_name", "amount", "currency",
        "error_reason",
    },
    SUBSCRIPTION_CANCELED_EMAILING_TYPE: {
        "front_url", "client_name", "plan_name", "effective_date",
    },
}


class TestFixtureContextDescriptionAlignment:
    """Verify context_description matches template variables."""

    @pytest.mark.parametrize("type_id,expected_keys", list(EXPECTED_CONTEXT_KEYS.items()))
    def test_context_description_contains_expected_keys(self, type_id, expected_keys):
        """Each fixture's context_description contains all expected template keys."""
        entry = _get_fixture_by_id(type_id)
        assert entry is not None, f"Fixture {type_id} not found"

        context_desc = entry["attributes"]["context_description"]
        context_keys = set(context_desc.keys())

        # Remove "user" key if present (it's for compute_context, not direct template vars)
        context_keys.discard("user")

        assert expected_keys.issubset(context_keys), (
            f"{type_id}: missing keys {expected_keys - context_keys} in context_description"
        )

    @pytest.mark.parametrize("type_id", [
        LICENSE_GRANTED_EMAILING_TYPE,
        LICENSE_REVOKED_EMAILING_TYPE,
    ])
    def test_license_types_have_user_description(self, type_id):
        """License types include 'user' key for private_data extraction."""
        entry = _get_fixture_by_id(type_id)
        context_desc = entry["attributes"]["context_description"]
        assert "user" in context_desc, f"{type_id} should have 'user' in context_description"

    @pytest.mark.parametrize("type_id", [
        SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE,
        SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE,
        SUBSCRIPTION_CANCELED_EMAILING_TYPE,
    ])
    def test_subscription_types_have_no_user_key(self, type_id):
        """Subscription types don't need 'user' key (batch service injects private_data)."""
        entry = _get_fixture_by_id(type_id)
        context_desc = entry["attributes"]["context_description"]
        assert "user" not in context_desc, (
            f"{type_id} should not have 'user' in context_description "
            f"(private_data injected by EmailingBatchService)"
        )


class TestFixtureRoleAssignment:
    """Verify role assignments on emailing types."""

    @pytest.mark.parametrize("type_id", [
        SUBSCRIPTION_PAYMENT_SUCCESS_EMAILING_TYPE,
        SUBSCRIPTION_PAYMENT_FAILED_EMAILING_TYPE,
        SUBSCRIPTION_CANCELED_EMAILING_TYPE,
    ])
    def test_subscription_types_have_license_admin_role(self, type_id):
        """Subscription types target LICENSE_ADMIN_ROLE."""
        from lys.apps.licensing.consts import LICENSE_ADMIN_ROLE

        entry = _get_fixture_by_id(type_id)
        assert "roles" in entry["attributes"], f"{type_id} missing 'roles' in attributes"
        assert LICENSE_ADMIN_ROLE in entry["attributes"]["roles"], (
            f"{type_id} should have {LICENSE_ADMIN_ROLE} in roles"
        )

    @pytest.mark.parametrize("type_id", [
        LICENSE_GRANTED_EMAILING_TYPE,
        LICENSE_REVOKED_EMAILING_TYPE,
    ])
    def test_license_types_have_no_roles(self, type_id):
        """License types don't have roles (sent to individual user)."""
        entry = _get_fixture_by_id(type_id)
        assert "roles" not in entry["attributes"], (
            f"{type_id} should not have 'roles' (sent to individual user)"
        )


class TestFixtureTemplateNames:
    """Verify fixture template names correspond to existing template files."""

    TEMPLATES_DIR = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "..",
        "templates", "emails"
    ))

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_all_fixture_templates_exist(self, lang):
        """Each fixture's template has a corresponding file in both languages."""
        for entry in EmailingTypeFixtures.data_list:
            template_name = entry["attributes"]["template"]
            template_path = os.path.join(self.TEMPLATES_DIR, lang, f"{template_name}.html")
            assert os.path.exists(template_path), (
                f"Template file missing: {lang}/{template_name}.html"
            )

    @pytest.mark.parametrize("lang", ["fr", "en"])
    def test_fixture_templates_render_with_context_description(self, lang):
        """Each fixture's template renders when context_description keys are provided as values."""
        env = Environment(loader=FileSystemLoader(self.TEMPLATES_DIR))

        for entry in EmailingTypeFixtures.data_list:
            template_name = entry["attributes"]["template"]
            context_desc = entry["attributes"]["context_description"]

            # Build a context with placeholder values for each key
            context = {}
            for key, value in context_desc.items():
                if key == "user":
                    # Simulate batch service enrichment
                    context["private_data"] = {
                        "first_name": "Test",
                        "last_name": "User",
                    }
                elif value is None:
                    context[key] = f"test_{key}_value"
                else:
                    context[key] = value

            # Always inject private_data (batch service does this for all templates)
            if "private_data" not in context:
                context["private_data"] = {
                    "first_name": "Test",
                    "last_name": "User",
                }

            # Ensure front_url is always present (used in CTA block)
            if "front_url" not in context:
                context["front_url"] = "https://test.example.com"

            template = env.get_template(f"{lang}/{template_name}.html")
            html = template.render(**context)
            assert len(html) > 0, (
                f"Template {lang}/{template_name}.html rendered empty"
            )
