"""
Unit tests for licensing client services structure.

Tests class structure and method signatures of LicensingClientService.
"""

import inspect

import pytest

pytest.importorskip("mollie", reason="mollie package not installed")

from lys.apps.licensing.modules.client.services import ClientService
from lys.apps.organization.modules.client.services import ClientService as OrgClientService


class TestClientServiceStructure:
    """Tests for licensing ClientService class structure."""

    def test_class_exists(self):
        assert ClientService is not None

    def test_inherits_from_org_client_service(self):
        assert issubclass(ClientService, OrgClientService)

    def test_has_create_client_with_owner(self):
        assert hasattr(ClientService, "create_client_with_owner")

    def test_has_assign_free_plan(self):
        assert hasattr(ClientService, "_assign_free_plan")


class TestClientServiceAsyncMethods:
    """Tests for async method signatures."""

    def test_create_client_with_owner_is_async(self):
        assert inspect.iscoroutinefunction(ClientService.create_client_with_owner)

    def test_assign_free_plan_is_async(self):
        assert inspect.iscoroutinefunction(ClientService._assign_free_plan)


class TestClientServiceSignatures:
    """Tests for method parameter signatures."""

    def test_create_client_with_owner_params(self):
        sig = inspect.signature(ClientService.create_client_with_owner)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "client_name" in params
        assert "email" in params
        assert "password" in params
        assert "language_id" in params

    def test_create_client_with_owner_optional_params(self):
        sig = inspect.signature(ClientService.create_client_with_owner)
        assert sig.parameters["send_verification_email"].default is True
        assert sig.parameters["first_name"].default is None
        assert sig.parameters["last_name"].default is None
        assert sig.parameters["gender_id"].default is None

    def test_assign_free_plan_params(self):
        sig = inspect.signature(ClientService._assign_free_plan)
        params = list(sig.parameters.keys())
        assert "client_id" in params
        assert "session" in params
