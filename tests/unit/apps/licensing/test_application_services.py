"""
Unit tests for license application service.
"""


class TestLicenseApplicationServiceStructure:
    """Tests for LicenseApplicationService class structure."""

    def test_service_exists(self):
        from lys.apps.licensing.modules.application.services import LicenseApplicationService
        assert LicenseApplicationService is not None

    def test_inherits_from_entity_service(self):
        from lys.apps.licensing.modules.application.services import LicenseApplicationService
        from lys.core.services import EntityService
        assert issubclass(LicenseApplicationService, EntityService)

    def test_service_name(self):
        from lys.apps.licensing.modules.application.services import LicenseApplicationService
        assert LicenseApplicationService.service_name == "license_application"
