"""
Unit tests for licensing application fixtures.

Tests LicenseApplicationDevFixtures structure and data.
"""

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.modules.application.fixtures import LicenseApplicationDevFixtures
from lys.apps.licensing.consts import DEFAULT_APPLICATION
from lys.core.consts.environments import EnvironmentEnum
from lys.core.fixtures import EntityFixtures
from lys.core.models.fixtures import ParametricEntityFixturesModel


class TestLicenseApplicationDevFixturesStructure:
    """Tests for LicenseApplicationDevFixtures class structure."""

    def test_class_exists(self):
        assert LicenseApplicationDevFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(LicenseApplicationDevFixtures, EntityFixtures)

    def test_model_is_parametric(self):
        assert LicenseApplicationDevFixtures.model is ParametricEntityFixturesModel

    def test_allowed_envs_contains_dev(self):
        assert EnvironmentEnum.DEV in LicenseApplicationDevFixtures._allowed_envs

    def test_allowed_envs_has_one_entry(self):
        assert len(LicenseApplicationDevFixtures._allowed_envs) == 1


class TestLicenseApplicationDevFixturesData:
    """Tests for fixture data content."""

    def test_data_list_is_list(self):
        assert isinstance(LicenseApplicationDevFixtures.data_list, list)

    def test_data_list_has_one_entry(self):
        assert len(LicenseApplicationDevFixtures.data_list) == 1

    def test_first_entry_id_is_default_application(self):
        assert LicenseApplicationDevFixtures.data_list[0]["id"] == DEFAULT_APPLICATION

    def test_first_entry_has_attributes(self):
        assert "attributes" in LicenseApplicationDevFixtures.data_list[0]

    def test_first_entry_enabled_is_true(self):
        assert LicenseApplicationDevFixtures.data_list[0]["attributes"]["enabled"] is True

    def test_first_entry_has_description(self):
        assert "description" in LicenseApplicationDevFixtures.data_list[0]["attributes"]
