"""
Unit tests for organization user inputs.

Tests Strawberry GraphQL input classes for user operations.
"""

import pytest


class TestUpdateClientUserEmailInputStructure:
    """Tests for UpdateClientUserEmailInput class structure."""

    def test_input_exists(self):
        """Test UpdateClientUserEmailInput class exists."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserEmailInput
        assert UpdateClientUserEmailInput is not None

    def test_has_new_email_field(self):
        """Test UpdateClientUserEmailInput has new_email field."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserEmailInput
        field_names = [f.name for f in UpdateClientUserEmailInput.__strawberry_definition__.fields]
        assert "new_email" in field_names

    def test_is_strawberry_pydantic_input(self):
        """Test UpdateClientUserEmailInput is a Strawberry Pydantic input."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserEmailInput

        assert hasattr(UpdateClientUserEmailInput, "__strawberry_definition__")
        assert UpdateClientUserEmailInput.__strawberry_definition__.is_input is True


class TestUpdateClientUserPrivateDataInputStructure:
    """Tests for UpdateClientUserPrivateDataInput class structure."""

    def test_input_exists(self):
        """Test UpdateClientUserPrivateDataInput class exists."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput
        assert UpdateClientUserPrivateDataInput is not None

    def test_has_first_name_field(self):
        """Test input has first_name field."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput
        field_names = [f.name for f in UpdateClientUserPrivateDataInput.__strawberry_definition__.fields]
        assert "first_name" in field_names

    def test_has_last_name_field(self):
        """Test input has last_name field."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput
        field_names = [f.name for f in UpdateClientUserPrivateDataInput.__strawberry_definition__.fields]
        assert "last_name" in field_names

    def test_has_gender_code_field(self):
        """Test input has gender_code field."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput
        field_names = [f.name for f in UpdateClientUserPrivateDataInput.__strawberry_definition__.fields]
        assert "gender_code" in field_names

    def test_has_language_code_field(self):
        """Test input has language_code field."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput
        field_names = [f.name for f in UpdateClientUserPrivateDataInput.__strawberry_definition__.fields]
        assert "language_code" in field_names

    def test_is_strawberry_pydantic_input(self):
        """Test UpdateClientUserPrivateDataInput is a Strawberry Pydantic input."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput

        assert hasattr(UpdateClientUserPrivateDataInput, "__strawberry_definition__")
        assert UpdateClientUserPrivateDataInput.__strawberry_definition__.is_input is True


class TestUpdateClientUserRolesInputStructure:
    """Tests for UpdateClientUserRolesInput class structure."""

    def test_input_exists(self):
        """Test UpdateClientUserRolesInput class exists."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserRolesInput
        assert UpdateClientUserRolesInput is not None

    def test_has_role_codes_field(self):
        """Test input has role_codes field."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserRolesInput
        field_names = [f.name for f in UpdateClientUserRolesInput.__strawberry_definition__.fields]
        assert "role_codes" in field_names

    def test_is_strawberry_pydantic_input(self):
        """Test UpdateClientUserRolesInput is a Strawberry Pydantic input."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserRolesInput

        assert hasattr(UpdateClientUserRolesInput, "__strawberry_definition__")
        assert UpdateClientUserRolesInput.__strawberry_definition__.is_input is True


class TestCreateClientUserInputStructure:
    """Tests for CreateClientUserInput class structure."""

    def test_input_exists(self):
        """Test CreateClientUserInput class exists."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        assert CreateClientUserInput is not None

    def test_has_client_id_field(self):
        """Test input has client_id field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "client_id" in field_names

    def test_has_email_field(self):
        """Test input has email field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "email" in field_names

    def test_has_password_field(self):
        """Test input has password field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "password" in field_names

    def test_has_language_code_field(self):
        """Test input has language_code field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "language_code" in field_names

    def test_has_first_name_field(self):
        """Test input has first_name field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "first_name" in field_names

    def test_has_last_name_field(self):
        """Test input has last_name field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "last_name" in field_names

    def test_has_gender_code_field(self):
        """Test input has gender_code field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "gender_code" in field_names

    def test_has_role_codes_field(self):
        """Test input has role_codes field."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput
        field_names = [f.name for f in CreateClientUserInput.__strawberry_definition__.fields]
        assert "role_codes" in field_names

    def test_is_strawberry_pydantic_input(self):
        """Test CreateClientUserInput is a Strawberry Pydantic input."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput

        assert hasattr(CreateClientUserInput, "__strawberry_definition__")
        assert CreateClientUserInput.__strawberry_definition__.is_input is True


class TestInputFieldDescriptions:
    """Tests for input field descriptions."""

    def test_update_email_input_fields_have_descriptions(self):
        """Test UpdateClientUserEmailInput fields have descriptions."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserEmailInput

        for field in UpdateClientUserEmailInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"

    def test_update_private_data_input_fields_have_descriptions(self):
        """Test UpdateClientUserPrivateDataInput fields have descriptions."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserPrivateDataInput

        for field in UpdateClientUserPrivateDataInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"

    def test_update_roles_input_fields_have_descriptions(self):
        """Test UpdateClientUserRolesInput fields have descriptions."""
        from lys.apps.organization.modules.user.inputs import UpdateClientUserRolesInput

        for field in UpdateClientUserRolesInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"

    def test_create_client_user_input_fields_have_descriptions(self):
        """Test CreateClientUserInput fields have descriptions."""
        from lys.apps.organization.modules.user.inputs import CreateClientUserInput

        for field in CreateClientUserInput.__strawberry_definition__.fields:
            assert field.description is not None, f"Field {field.name} has no description"


class TestInputToPydanticMethods:
    """Tests for to_pydantic conversion methods."""

    def test_all_inputs_have_to_pydantic(self):
        """Test all input classes have to_pydantic method."""
        from lys.apps.organization.modules.user.inputs import (
            UpdateClientUserEmailInput,
            UpdateClientUserPrivateDataInput,
            UpdateClientUserRolesInput,
            CreateClientUserInput
        )

        assert hasattr(UpdateClientUserEmailInput, "to_pydantic")
        assert hasattr(UpdateClientUserPrivateDataInput, "to_pydantic")
        assert hasattr(UpdateClientUserRolesInput, "to_pydantic")
        assert hasattr(CreateClientUserInput, "to_pydantic")
