"""
Unit tests for licensing role module fixtures.
"""
from lys.apps.licensing.modules.role.fixtures import (
    LicensingRoleFixtures,
    LICENSE_ADMIN_ROLE_WEBSERVICES,
)


class TestLicensingRoleFixtures:
    def test_exists(self):
        assert LicensingRoleFixtures is not None

    def test_has_data_list(self):
        assert LicensingRoleFixtures.data_list is not None
        assert len(LicensingRoleFixtures.data_list) == 1

    def test_delete_previous_data_is_false(self):
        assert LicensingRoleFixtures.delete_previous_data is False


class TestLicenseAdminRoleWebservices:
    def test_is_list(self):
        assert isinstance(LICENSE_ADMIN_ROLE_WEBSERVICES, list)

    def test_contains_expected_webservices(self):
        assert "all_clients" in LICENSE_ADMIN_ROLE_WEBSERVICES
        assert "subscription" in LICENSE_ADMIN_ROLE_WEBSERVICES
