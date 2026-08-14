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
