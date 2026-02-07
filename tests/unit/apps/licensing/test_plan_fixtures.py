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

    def test_data_list_has_plans(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        assert len(LicensePlanDevFixtures.data_list) >= 3

    def test_data_list_contains_free_plan(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        ids = [entry["id"] for entry in LicensePlanDevFixtures.data_list]
        assert "FREE" in ids

    def test_data_list_contains_starter_plan(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        ids = [entry["id"] for entry in LicensePlanDevFixtures.data_list]
        assert "STARTER" in ids

    def test_data_list_contains_pro_plan(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanDevFixtures
        ids = [entry["id"] for entry in LicensePlanDevFixtures.data_list]
        assert "PRO" in ids

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

    def test_data_list_has_versions(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        assert len(LicensePlanVersionDevFixtures.data_list) >= 3

    def test_has_format_rules_method(self):
        from lys.apps.licensing.modules.plan.fixtures import LicensePlanVersionDevFixtures
        assert hasattr(LicensePlanVersionDevFixtures, "format_rules")
