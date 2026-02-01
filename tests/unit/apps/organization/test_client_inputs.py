"""
Unit tests for organization client inputs.

Tests Strawberry GraphQL input classes for client operations.
"""

import pytest


class TestCreateClientInputStructure:
    """Tests for CreateClientInput class structure."""

    def test_create_client_input_exists(self):
        """Test CreateClientInput class exists."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        assert CreateClientInput is not None

    def test_create_client_input_has_client_name_field(self):
        """Test CreateClientInput has client_name field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        assert hasattr(CreateClientInput, "__strawberry_definition__")
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "client_name" in field_names

    def test_create_client_input_has_email_field(self):
        """Test CreateClientInput has email field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "email" in field_names

    def test_create_client_input_has_password_field(self):
        """Test CreateClientInput has password field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "password" in field_names

    def test_create_client_input_has_language_code_field(self):
        """Test CreateClientInput has language_code field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "language_code" in field_names

    def test_create_client_input_has_first_name_field(self):
        """Test CreateClientInput has first_name field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "first_name" in field_names

    def test_create_client_input_has_last_name_field(self):
        """Test CreateClientInput has last_name field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "last_name" in field_names

    def test_create_client_input_has_gender_code_field(self):
        """Test CreateClientInput has gender_code field."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        field_names = [f.name for f in CreateClientInput.__strawberry_definition__.fields]
        assert "gender_code" in field_names


class TestCreateClientInputPydanticModel:
    """Tests for CreateClientInput Pydantic model binding."""

    def test_create_client_input_is_pydantic_input(self):
        """Test CreateClientInput is a Strawberry Pydantic input."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput

        # Verify it has the strawberry definition
        assert hasattr(CreateClientInput, "__strawberry_definition__")
        # Verify it's based on a pydantic model
        assert hasattr(CreateClientInput.__strawberry_definition__, "is_input")
        assert CreateClientInput.__strawberry_definition__.is_input is True

    def test_create_client_input_has_to_pydantic_method(self):
        """Test CreateClientInput has to_pydantic method."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput
        assert hasattr(CreateClientInput, "to_pydantic")


class TestUpdateClientInputStructure:
    """Tests for UpdateClientInput class structure."""

    def test_update_client_input_exists(self):
        """Test UpdateClientInput class exists."""
        from lys.apps.organization.modules.client.inputs import UpdateClientInput
        assert UpdateClientInput is not None

    def test_update_client_input_has_name_field(self):
        """Test UpdateClientInput has name field."""
        from lys.apps.organization.modules.client.inputs import UpdateClientInput
        field_names = [f.name for f in UpdateClientInput.__strawberry_definition__.fields]
        assert "name" in field_names


class TestUpdateClientInputPydanticModel:
    """Tests for UpdateClientInput Pydantic model binding."""

    def test_update_client_input_is_pydantic_input(self):
        """Test UpdateClientInput is a Strawberry Pydantic input."""
        from lys.apps.organization.modules.client.inputs import UpdateClientInput

        assert hasattr(UpdateClientInput, "__strawberry_definition__")
        assert hasattr(UpdateClientInput.__strawberry_definition__, "is_input")
        assert UpdateClientInput.__strawberry_definition__.is_input is True

    def test_update_client_input_has_to_pydantic_method(self):
        """Test UpdateClientInput has to_pydantic method."""
        from lys.apps.organization.modules.client.inputs import UpdateClientInput
        assert hasattr(UpdateClientInput, "to_pydantic")


class TestInputFieldDescriptions:
    """Tests for input field descriptions."""

    def test_create_client_input_fields_have_descriptions(self):
        """Test CreateClientInput fields have descriptions."""
        from lys.apps.organization.modules.client.inputs import CreateClientInput

        for field in CreateClientInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"

    def test_update_client_input_fields_have_descriptions(self):
        """Test UpdateClientInput fields have descriptions."""
        from lys.apps.organization.modules.client.inputs import UpdateClientInput

        for field in UpdateClientInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"
