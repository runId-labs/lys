"""
Unit tests for licensing plan fixtures.
"""
import pytest

mollie_available = pytest.importorskip("mollie", reason="mollie package not installed") is not None


class TestLicensePlanDevFixtures:
    """Tests for LicensePlanDevFixtures."""

    def test_fixture_class_exists(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        assert LicensePlanDevFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(LicensePlanDevFixtures, EntityFixtures)

    def test_data_list_exists(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        assert hasattr(LicensePlanDevFixtures, "data_list")
        assert isinstance(LicensePlanDevFixtures.data_list, list)

    def test_ships_only_the_free_plan(self):
        """Commercial tiers belong to each application, the framework only needs FREE."""
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        assert [entry["id"] for entry in LicensePlanDevFixtures.data_list] == ["FREE"]

    def test_does_not_disable_unlisted_plans(self):
        """
        Custom plans negotiated with a single client are created at runtime and
        appear in no data_list; sweeping would silently disable them.
        """
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        assert LicensePlanDevFixtures.delete_previous_data is False

    def test_data_list_contains_free_plan(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        ids = [entry["id"] for entry in LicensePlanDevFixtures.data_list]
        assert "FREE" in ids

    def test_all_entries_have_attributes(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        for entry in LicensePlanDevFixtures.data_list:
            assert "attributes" in entry


class TestLicensePlanVersionDevFixtures:
    """Tests for LicensePlanVersionDevFixtures."""

    def test_fixture_class_exists(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        assert LicensePlanVersionDevFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        from lys.core.fixtures import EntityFixtures
        assert issubclass(LicensePlanVersionDevFixtures, EntityFixtures)

    def test_data_list_exists(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        assert hasattr(LicensePlanVersionDevFixtures, "data_list")
        assert isinstance(LicensePlanVersionDevFixtures.data_list, list)

    def test_versions_only_the_free_plan(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        plan_ids = [
            entry["attributes"]["plan_id"]
            for entry in LicensePlanVersionDevFixtures.data_list
        ]
        assert plan_ids == ["FREE"]

    def test_has_format_rules_method(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        assert hasattr(LicensePlanVersionDevFixtures, "format_rules")


class TestCatalogueAdministrationWebservices:
    """The catalogue mutations must exist and be reachable by the admin role."""

    def test_listing_query_is_registered(self):
        """Without it, the version IDs the mutations take cannot be discovered."""
        from lys.apps.licensing.modules.plan.webservices import LicensePlanQuery

        for query in ("all_license_plans", "all_license_plan_versions"):
            assert hasattr(LicensePlanQuery, query)

    def test_mutations_are_registered(self):
        from lys.apps.licensing.modules.plan.webservices import LicensePlanVersionMutation

        for mutation in (
            "create_license_plan_version",
            "set_license_plan_version_rule",
            "set_license_plan_version_enabled",
        ):
            assert hasattr(LicensePlanVersionMutation, mutation)

    def test_admin_role_grants_them(self):
        """
        A mutation absent from the role's list is unreachable, so adding one
        without granting it would ship a dead webservice.
        """
        from lys.apps.licensing.modules.role.fixtures import LICENSE_ADMIN_ROLE_WEBSERVICES

        for webservice in (
            "subscribe_client_manually",
            "set_subscription_billing_mode",
            "all_license_plans",
            "all_license_plan_versions",
            "create_license_plan_version",
            "set_license_plan_version_rule",
            "set_license_plan_version_enabled",
        ):
            assert webservice in LICENSE_ADMIN_ROLE_WEBSERVICES
