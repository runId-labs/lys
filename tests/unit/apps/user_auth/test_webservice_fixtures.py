"""
Unit tests for user_auth webservice module fixtures.
"""
from lys.apps.user_auth.modules.webservice.fixtures import (
    WebservicePublicTypeFixtures,
    WebserviceFixtures,
)
from lys.core.fixtures import EntityFixtures


class TestWebservicePublicTypeFixtures:
    def test_exists(self):
        assert WebservicePublicTypeFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(WebservicePublicTypeFixtures, EntityFixtures)

    def test_has_data_list(self):
        assert WebservicePublicTypeFixtures.data_list is not None
        assert len(WebservicePublicTypeFixtures.data_list) == 2

    def test_has_model(self):
        assert WebservicePublicTypeFixtures.model is not None

    def test_data_list_contains_no_limitation(self):
        from lys.core.consts.webservices import NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE
        ids = [d["id"] for d in WebservicePublicTypeFixtures.data_list]
        assert NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE in ids

    def test_data_list_contains_disconnected(self):
        from lys.core.consts.webservices import DISCONNECTED_WEBSERVICE_PUBLIC_TYPE
        ids = [d["id"] for d in WebservicePublicTypeFixtures.data_list]
        assert DISCONNECTED_WEBSERVICE_PUBLIC_TYPE in ids


class TestWebserviceFixtures:
    def test_exists(self):
        assert WebserviceFixtures is not None

    def test_inherits_from_entity_fixtures(self):
        assert issubclass(WebserviceFixtures, EntityFixtures)

    def test_has_format_public_type_method(self):
        assert hasattr(WebserviceFixtures, "format_public_type")

    def test_has_format_access_levels_method(self):
        assert hasattr(WebserviceFixtures, "format_access_levels")
