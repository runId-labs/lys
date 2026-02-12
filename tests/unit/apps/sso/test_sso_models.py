"""
Unit tests for SSO Pydantic input models.

Tests cover:
- CreateClientWithSSOInputModel validation (sso_token, client_name, language_code)
- Field boundary validation (min_length, max_length)
- Language code format validation

Test approach: Unit (pure Pydantic validation, no database)
"""

import pytest
from pydantic import ValidationError

from lys.apps.organization.modules.client.models import CreateClientWithSSOInputModel


class TestCreateClientWithSSOInputModel:
    """Tests for SSO client creation input model."""

    def test_valid_input(self):
        model = CreateClientWithSSOInputModel(
            sso_token="abc123",
            client_name="My Company",
            language_code="en",
        )
        assert model.sso_token == "abc123"
        assert model.client_name == "My Company"
        assert model.language_code == "en"

    def test_valid_input_with_optional_fields(self):
        model = CreateClientWithSSOInputModel(
            sso_token="abc123",
            client_name="My Company",
            language_code="en",
            first_name="John",
            last_name="Doe",
            gender_code="MALE",
        )
        assert model.first_name == "John"
        assert model.last_name == "Doe"
        assert model.gender_code == "MALE"

    def test_optional_fields_default_to_none(self):
        model = CreateClientWithSSOInputModel(
            sso_token="abc123",
            client_name="My Company",
            language_code="en",
        )
        assert model.first_name is None
        assert model.last_name is None
        assert model.gender_code is None

    def test_empty_sso_token_rejected(self):
        with pytest.raises(ValidationError):
            CreateClientWithSSOInputModel(
                sso_token="",
                client_name="My Company",
                language_code="en",
            )

    def test_missing_sso_token_rejected(self):
        with pytest.raises(ValidationError):
            CreateClientWithSSOInputModel(
                client_name="My Company",
                language_code="en",
            )

    def test_empty_client_name_rejected(self):
        with pytest.raises(ValidationError):
            CreateClientWithSSOInputModel(
                sso_token="abc123",
                client_name="",
                language_code="en",
            )

    def test_whitespace_only_client_name_rejected(self):
        with pytest.raises(ValidationError):
            CreateClientWithSSOInputModel(
                sso_token="abc123",
                client_name="   ",
                language_code="en",
            )

    def test_client_name_stripped(self):
        model = CreateClientWithSSOInputModel(
            sso_token="abc123",
            client_name="  My Company  ",
            language_code="en",
        )
        assert model.client_name == "My Company"

    def test_client_name_max_length(self):
        with pytest.raises(ValidationError):
            CreateClientWithSSOInputModel(
                sso_token="abc123",
                client_name="x" * 256,
                language_code="en",
            )

    def test_language_code_valid_two_letter(self):
        model = CreateClientWithSSOInputModel(
            sso_token="abc123",
            client_name="My Company",
            language_code="fr",
        )
        assert model.language_code == "fr"

    def test_language_code_valid_with_region(self):
        model = CreateClientWithSSOInputModel(
            sso_token="abc123",
            client_name="My Company",
            language_code="en-us",
        )
        assert model.language_code == "en-us"

    def test_language_code_too_short(self):
        with pytest.raises((ValidationError, Exception)):
            CreateClientWithSSOInputModel(
                sso_token="abc123",
                client_name="My Company",
                language_code="e",
            )

    def test_language_code_invalid_format(self):
        with pytest.raises(Exception):
            CreateClientWithSSOInputModel(
                sso_token="abc123",
                client_name="My Company",
                language_code="english",
            )
