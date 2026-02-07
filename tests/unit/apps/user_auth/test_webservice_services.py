"""
Unit tests for user_auth webservice services.

Tests structure and method signatures of AuthWebserviceService
and WebservicePublicTypeService.
"""

import inspect

from lys.apps.user_auth.modules.webservice.services import (
    AuthWebserviceService,
    WebservicePublicTypeService,
)
from lys.apps.base.modules.webservice.services import WebserviceService
from lys.core.services import EntityService


class TestWebservicePublicTypeServiceStructure:
    """Tests for WebservicePublicTypeService class."""

    def test_class_exists(self):
        assert WebservicePublicTypeService is not None

    def test_inherits_from_entity_service(self):
        assert issubclass(WebservicePublicTypeService, EntityService)


class TestAuthWebserviceServiceStructure:
    """Tests for AuthWebserviceService class structure."""

    def test_class_exists(self):
        assert AuthWebserviceService is not None

    def test_inherits_from_webservice_service(self):
        assert issubclass(AuthWebserviceService, WebserviceService)

    def test_has_accessible_webservices_or_where(self):
        assert hasattr(AuthWebserviceService, "_accessible_webservices_or_where")

    def test_has_accessible_webservices(self):
        assert hasattr(AuthWebserviceService, "accessible_webservices")

    def test_has_get_user_access_levels(self):
        assert hasattr(AuthWebserviceService, "get_user_access_levels")


class TestAuthWebserviceServiceAsyncMethods:
    """Tests for async method signatures."""

    def test_accessible_webservices_or_where_is_async(self):
        assert inspect.iscoroutinefunction(AuthWebserviceService._accessible_webservices_or_where)

    def test_accessible_webservices_is_async(self):
        assert inspect.iscoroutinefunction(AuthWebserviceService.accessible_webservices)

    def test_get_user_access_levels_is_async(self):
        assert inspect.iscoroutinefunction(AuthWebserviceService.get_user_access_levels)


class TestAuthWebserviceServiceSignatures:
    """Tests for method parameter signatures."""

    def test_accessible_webservices_or_where_params(self):
        sig = inspect.signature(AuthWebserviceService._accessible_webservices_or_where)
        params = list(sig.parameters.keys())
        assert "stmt" in params
        assert "user" in params

    def test_accessible_webservices_params(self):
        sig = inspect.signature(AuthWebserviceService.accessible_webservices)
        params = list(sig.parameters.keys())
        assert "user" in params

    def test_get_user_access_levels_params(self):
        sig = inspect.signature(AuthWebserviceService.get_user_access_levels)
        params = list(sig.parameters.keys())
        assert "webservice" in params
        assert "user" in params
        assert "session" in params
